"""Run the whole pipeline: PDF -> .md -> .json -> .csv.

Usage:
    python main.py              # every PDF in data/input/pdf
    python main.py some.pdf     # a single file

Outputs go to data/output/{_md,_json,_csv}; one metrics row per PDF is appended
to data/logs/metrics_log.csv. A failing PDF is reported and skipped, so one bad
file does not stop the batch.
"""

from __future__ import annotations

import csv
import sys
import time
from datetime import datetime
from pathlib import Path

from extract import extract
from pdf_to_markdown import pdf_to_markdown
from pricing import cost_usd
from settings import get_settings
from to_csv import statement_to_rows, write_csv

settings = get_settings()

MD_OUTPUT_DIR = settings.output_dir / "_md"
JSON_OUTPUT_DIR = settings.output_dir / "_json"
CSV_OUTPUT_DIR = settings.output_dir / "_csv"
METRICS_LOG = settings.logs_dir / "metrics_log.csv"


def _append_metrics(metrics: dict) -> None:
    """Append one row per run; write the header only when the file is new."""
    new_file = not METRICS_LOG.exists()
    with open(METRICS_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics.keys()))
        if new_file:
            writer.writeheader()
        writer.writerow(metrics)


def run(pdf_path: str | Path) -> None:
    pdf_path = Path(pdf_path)
    stem = pdf_path.stem
    t_start = time.perf_counter()

    # 1. PDF -> Markdown (Docling)
    t0 = time.perf_counter()
    md = pdf_to_markdown(pdf_path)
    docling_seconds = time.perf_counter() - t0
    (MD_OUTPUT_DIR / f"{stem}.md").write_text(md, encoding="utf-8")

    # 2. Markdown -> structured JSON (one PydanticAI call)
    t1 = time.perf_counter()
    statement, usage = extract(md)
    llm_seconds = time.perf_counter() - t1
    (JSON_OUTPUT_DIR / f"{stem}.json").write_text(
        statement.model_dump_json(indent=2), encoding="utf-8"
    )

    # 3 + 4. Transform + JSON -> CSV
    rows = statement_to_rows(statement)
    write_csv(rows, CSV_OUTPUT_DIR / f"{stem}.csv")

    # --- observability record ---
    metrics = {
        "file": pdf_path.name,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "model": settings.llm_model,
        "docling_seconds": round(docling_seconds, 2),
        "llm_seconds": round(llm_seconds, 2),
        "total_seconds": round(time.perf_counter() - t_start, 2),
        "input_tokens": usage["input_tokens"],
        "cached_tokens": usage["cached_tokens"],
        "output_tokens": usage["output_tokens"],
        "total_tokens": usage["total_tokens"],
        "cost_usd": round(cost_usd(usage, settings.llm_model), 6),
        "rows": len(rows),
    }
    print(
        f"{pdf_path.name}: docling {metrics['docling_seconds']}s | "
        f"llm {metrics['llm_seconds']}s | total {metrics['total_seconds']}s | "
        f"tokens {usage['input_tokens']} (cached {usage['cached_tokens']})"
        f"+{usage['output_tokens']}={usage['total_tokens']} | ~${metrics['cost_usd']}"
    )
    _append_metrics(metrics)


def main(argv: list[str]) -> int:
    for path in (settings.input_dir, MD_OUTPUT_DIR, JSON_OUTPUT_DIR, CSV_OUTPUT_DIR, settings.logs_dir):
        path.mkdir(parents=True, exist_ok=True)

    pdf_files = [Path(a) for a in argv] or sorted(settings.input_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {settings.input_dir}")
        return 0

    failed = 0
    for pdf_file in pdf_files:
        try:
            run(pdf_file)
        except Exception as e:  # keep going; report at the end
            failed += 1
            print(f"{pdf_file.name}: FAILED - {type(e).__name__}: {e}", file=sys.stderr)

    print(f"Done: {len(pdf_files) - failed} ok, {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
