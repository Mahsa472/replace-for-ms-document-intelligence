"""Step 1: PDF -> Markdown with Docling."""

from __future__ import annotations

from functools import cache
from pathlib import Path

import httpx

from settings import get_settings


@cache
def _client() -> httpx.Client:
    s = get_settings()
    key = s.docling_api_key
    return httpx.Client(
        base_url=s.docling_base_url,
        headers={"X-Api-Key": key.get_secret_value()} if key else None,
        timeout=s.docling_timeout,
    )


def pdf_to_markdown(pdf_path: str | Path, **options: str) -> str:
    """Convert a PDF to Markdown text using Docling.

    Docling keeps the table structure, which is what lets the LLM tell the
    '100% Amounts' column apart from the 'Your Share' column.
    Extra keyword arguments override the default Docling convert options.
    """
    pdf_path = Path(pdf_path)
    with pdf_path.open("rb") as f:
        response = _client().post(
            "/v1/convert/file",
            files={"files": (pdf_path.name, f, "application/pdf")},
            data={
                "to_formats": "md",
                "do_ocr": "false",
                "do_table_structure": "true",
                "table_mode": "accurate",
                "image_export_mode": "placeholder",  # do not extract the images if you don't need, it makes extra tokens!
                **options,
            },
        )

    if response.is_error:
        raise RuntimeError(
            f"Docling HTTP {response.status_code} for {pdf_path.name}: {response.text}"
        )

    body = response.json()
    if body.get("status") != "success":
        raise RuntimeError(f"Docling failed for {pdf_path.name}: {body.get('errors')}")
    return body["document"]["md_content"]
