"""Step 1: PDF -> Markdown with Docling."""

from __future__ import annotations

import os
from pathlib import Path

import httpx

_api_key = os.environ.get("DOCLING_API_KEY")

_client = httpx.Client(
    base_url=os.environ.get("DOCLING_BASE_URL", "http://docling:5001"),
    headers={"X-Api-Key": _api_key} if _api_key else None,
    timeout=620,  # a bit longer than DOCLING_SERVE_MAX_SYNC_WAIT (600)
)


def pdf_to_markdown(pdf_path: str | Path, **options: str) -> str:
    """Convert a PDF to Markdown text using Docling.

    Docling keeps the table structure, which is what lets the LLM tell the
    '100% Amounts' column apart from the 'Your Share' column.
    Extra keyword arguments override the default Docling convert options.
    """
    pdf_path = Path(pdf_path)
    with pdf_path.open("rb") as f:
        response = _client.post(
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
