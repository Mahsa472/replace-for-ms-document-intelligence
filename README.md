# replace-for-ms-document-intelligence

Extract structured data from PDFs **without a cloud form-recognition service** (e.g. Azure Document Intelligence):

- **[Docling](https://github.com/docling-project/docling-serve)** (open source, runs locally in Docker) converts the PDF to Markdown and keeps table structure.
- **One LLM call** ([PydanticAI](https://ai.pydantic.dev/), any OpenAI-compatible model) fills a typed Pydantic schema.
- Plain Python applies business rules and writes a CSV.

The example targets **reinsurance treaty balance statements** from brokers, but steps 1–2 work with any schema.

## Pipeline

```
PDF ─► [1] Docling ─► Markdown ─► [2] LLM + schema ─► JSON ─► [3] transform ─► [4] CSV
```

| Step | File | Purpose |
|------|------|---------|
| 1 | `pdf_to_markdown.py` | PDF → Markdown via the Docling server (OCR off, accurate tables) |
| 2 | `extract.py` | Detect broker, build prompt, **one** PydanticAI call validated against `schema.py` (auto-retry on errors) |
| 3 | `transform.py` | Business rules: masking, main class, sign detection, outstanding-loss handling |
| 4 | `to_csv.py` | One CSV row per statement row (`;`, decimal comma, `DD.MM.YYYY`) |

`main.py` runs everything and logs timing, tokens and estimated cost per PDF.

**One schema, one prompt per broker.** The output is always the same, so there is a single schema.
Only the layout differs per broker, described in `prompts/<broker>.txt`. Broker detection is
deterministic: signature strings (name, email domain) are matched in the Markdown.

## Structure

```
.devcontainer/          app container + docling-serve sidecar
src/
  main.py               run the pipeline
  settings.py           configuration (pydantic-settings)
  pdf_to_markdown.py    step 1
  extract.py            step 2
  brokers.py            broker registry + detection
  schema.py             output schema
  transform.py          step 3 (your rules)
  to_csv.py             step 4
  pricing.py            token prices -> cost
  prompts/              _base.txt (shared rules) + one file per broker
  data/                 input/pdf, output/{_md,_json,_csv}, logs, cache (git-ignored)
```

## Setup

Requires Docker Desktop, VS Code with *Dev Containers*, and an OpenAI-compatible LLM endpoint.

```bash
cp .devcontainer/.devcontainer.env.example .devcontainer/.devcontainer.env   # Docling
cp src/credentials.env.example src/credentials.env                           # LLM
```

| File | Variables |
|------|-----------|
| `.devcontainer/.devcontainer.env` | `DOCLING_BASE_URL` (default `http://docling:5001`), `DOCLING_API_KEY` (optional) |
| `src/credentials.env` | `LLM_MODEL`, `LLM_API_KEY` (required), `LLM_BASE_URL` (empty = OpenAI) |

### Fully local (no data leaves your machine, no API cost)

Docling already runs locally. Point the LLM at a local OpenAI-compatible server
(e.g. [Ollama](https://ollama.com), vLLM, LM Studio) and the whole pipeline runs
**100% on your machine with no API cost**:

```env
# src/credentials.env — Ollama running on the host
LLM_MODEL=<a local model, e.g. one pulled with `ollama pull`>
LLM_API_KEY=ollama            # any non-empty value
LLM_BASE_URL=http://host.docker.internal:11434/v1
```

Pick a model that supports structured output / tool calling; larger models give
noticeably better extraction quality.

Then **Reopen in Container**. The first build pulls the Docling image (a few GB).
Docling is also available at <http://localhost:5001/docs> and <http://localhost:5001/ui>.

## Run

```bash
cd src
python main.py              # all PDFs in data/input/pdf
python main.py a.pdf b.pdf  # specific files
```

```
statement_01.pdf: docling 14.2s | llm 9.8s | total 24.1s | tokens 5210 (cached 3840)+890=6100 | ~$0.0123
Done: 1 ok, 0 failed.
```

Failing PDFs are reported and skipped (exit code 1). Outputs per PDF: `_md/`, `_json/`, `_csv/`
under `data/output/`, plus one row in `data/logs/metrics_log.csv`.

## Schema

```
AccountStatement
├── broker_name, statement_date, treaty_name, line_of_business,
│   contract_reference, document_reference, account_id, share_percent
├── cedent: Party
├── period: StatementPeriod (accounting_start/end, coverage_start/end)
└── sections: [StatementSection]  (title, currency, balance)
    └── rows: [StatementRow]      (category, printed_label, amount_total, amount_share)
```

Amounts are signed (CR +, DR −) with 2 decimals; dates are ISO in JSON and formatted only in the CSV.

## Customising

- **New broker:** copy `prompts/broker1.txt`, adjust the field locations, add a `Broker(...)` entry in `brokers.py`. No schema or CSV changes.
- **New rule:** add a function to `transform.py` and call it in `statement_to_rows()` (`to_csv.py`).
- **Other CSV format:** edit `COLUMNS` and the row dict in `to_csv.py`; locale via `format_value()`.
- **Other document type:** replace `schema.py`, the prompts and `to_csv.py`.

## Cost & performance

- Fill in model prices (USD / 1M tokens) in `pricing.py`; unknown models count as 0.
- One agent per broker is reused and sends a per-broker `prompt_cache_key`, so the shared prompt is cached — see `cached_tokens` in the metrics log.
- Docling on CPU is the slowest step. Limits (600 s, 200 pages, 100 MB, 6 GB RAM) are in `docker-compose.yml`; pin the image tag for reproducible builds.
