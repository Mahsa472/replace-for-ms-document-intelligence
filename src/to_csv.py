"""Step 4: structured object -> CSV.

All deterministic (no LLM). The nested sections are flattened into one CSV row
per statement row; header fields are copied down, and main class / currency come
from each row's own section. Business rules live in transform.py.

To match your own target file, edit COLUMNS and the dict in statement_to_rows().
"""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from schema import AccountStatement
from transform import (
    apply_outstanding_loss_logic,
    detect_signs,
    is_summary_row,
    main_class,
    mask_percent,
    mask_year_in_ref,
    to_decimal,
)

# Header of the output file (order = column order).
COLUMNS = [
    "BROKER", "CEDENT", "TREATY", "CONTRACT_REFERENCE", "SHARE_PERCENT",
    "ACCOUNTING_PERIOD_END", "ACCOUNTING_YEAR", "UW_YEAR", "OCC_YEAR",
    "DOCUMENT_REFERENCE", "MAIN_CLASS", "ACCOUNT_CLASS", "CURRENCY", "AMOUNT",
]

# Columns that need a non-default number of decimals.
DECIMALS = {"SHARE_PERCENT": 3}


def format_value(
    value: object,
    decimals: int = 2,
    decimal_sep: str = ",",
    date_format: str = "%d.%m.%Y",
) -> str:
    """Format one cell. Defaults are German style (1234,50 and 31.12.2026); None -> ''."""
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime(date_format)
    if isinstance(value, (Decimal, int, float)) and not isinstance(value, bool):
        return format(Decimal(str(value)), f".{decimals}f").replace(".", decimal_sep)
    return str(value)


def statement_to_rows(statement: AccountStatement) -> list[dict]:
    """One output row per statement row, across ALL sections.

    Summary rows ('Due to you', 'Balance', ...) and zero amounts are dropped.
    """
    period = statement.period
    coverage_year = str(period.coverage_start.year) if period.coverage_start else None
    accounting_year = str(period.accounting_end.year) if period.accounting_end else None

    rows: list[dict] = []
    for section in statement.sections:
        # Our share: the share column, else 100% amount x share %, else 0.
        amounts = [
            r.amount_share if r.amount_share is not None
            else r.amount_total * statement.share_percent / 100
            if r.amount_total is not None and statement.share_percent is not None
            else 0
            for r in section.rows
        ]
        labels = [r.printed_label or r.category for r in section.rows]
        signed = detect_signs(amounts, labels, section.balance)

        for r, amount in zip(section.rows, signed):
            account_class, amount = apply_outstanding_loss_logic(
                mask_percent(r.printed_label), amount, period.accounting_end
            )
            if is_summary_row(account_class) or not to_decimal(amount):
                continue
            rows.append({
                "BROKER": statement.broker_name,
                "CEDENT": statement.cedent.name,
                "TREATY": statement.treaty_name,
                "CONTRACT_REFERENCE": mask_year_in_ref(statement.contract_reference, coverage_year),
                "SHARE_PERCENT": statement.share_percent,
                "ACCOUNTING_PERIOD_END": period.accounting_end,
                "ACCOUNTING_YEAR": accounting_year,
                "UW_YEAR": coverage_year,
                "OCC_YEAR": coverage_year,
                "DOCUMENT_REFERENCE": statement.document_reference,
                "MAIN_CLASS": main_class(statement, section),
                "ACCOUNT_CLASS": account_class,
                "CURRENCY": section.currency,
                "AMOUNT": amount,
            })
    return rows


def write_csv(rows: list[dict], out_path: str | Path, delimiter: str = ";") -> None:
    """Write rows with COLUMNS as header (UTF-8 with BOM so Excel opens it correctly)."""
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=delimiter, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: format_value(v, DECIMALS.get(k, 2)) for k, v in row.items()})
