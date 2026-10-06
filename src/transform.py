"""Step 3: optional post-extraction transformations.

This is the place to add your own business rules on top of the extracted data
(masking, renaming, sign fixes, ...). Every function is pure: it takes values
and returns new values, so rules can be combined freely in to_csv.py.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from itertools import product
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schema import AccountStatement, StatementSection


def _to_decimal(value: object) -> Decimal | None:
    """Best-effort Decimal conversion; None when the value is empty or not numeric."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


# ---- Text masking ----------------------------------------------------------

def mask_percent(text: str | None) -> str | None:
    """'Brokerage at 2.5%' -> 'Brokerage at x%'."""
    if not text:
        return text
    return re.sub(r"\d+(?:\.\d+)?%", "x%", text)


def mask_year_in_ref(ref: str | None, year_full: str | int | None) -> str | None:
    """Replace the first 2-digit year in a reference: 'RR-0001-26X' + 2026 -> 'RR-0001-__X'."""
    if not ref or not year_full:
        return ref
    yy = str(year_full)[-2:]
    return ref.replace(yy, "__", 1)


# ---- Classification ---------------------------------------------------------

def main_class(statement: AccountStatement, section: StatementSection) -> str:
    """Line of business + section title, e.g. 'Non Marine Section A'."""
    return " ".join(p for p in (statement.line_of_business, section.title) if p).strip()


def is_balance_class(value: object) -> bool:
    """True when the accounting class text contains 'balance'."""
    return isinstance(value, str) and "balance" in value.casefold()


# ---- Business rules ---------------------------------------------------------

def apply_outstanding_loss_logic(
    account_name: str | None,
    amount: object,
    accounting_period_end: date | datetime | None,
) -> tuple[str | None, object]:
    """Example rule for 'outstanding loss' rows.

    - the amount is always negative (a positive value is flipped; the type is kept);
    - if the accounting period ended in a previous year, ' stat' is appended to the name.
    """
    if not account_name:
        return account_name, amount

    name = account_name.strip()
    if "outstanding loss" not in name.casefold():
        return name, amount

    value = _to_decimal(amount.strip().replace(",", ".") if isinstance(amount, str) else amount)
    if value is not None and value > 0:
        amount = f"-{amount.strip()}" if isinstance(amount, str) else -amount

    if (
        accounting_period_end
        and accounting_period_end.year < date.today().year
        and not name.casefold().endswith(" stat")
    ):
        name = f"{name} stat"

    return name, amount


def detect_signs(amounts: list[object], labels: list[str | None], balance: object) -> list[object]:
    """Choose row signs so the rows add up to the section balance.

    Pass 1: every row counts; find the ONE sign combination whose sum equals balance.
    Pass 2 (only if pass 1 finds nothing): one row is treated as not part of the
            sum (it is kept negative) and the rest must equal balance.
    'Outstanding' rows are never changed. If no unique solution exists, the
    original amounts are returned unchanged.
    Cost grows with 2^rows, which is fine for typical statements (< ~15 rows).
    """
    target = _to_decimal(balance)
    if target is None or len(amounts) != len(labels):
        return amounts

    parsed = [_to_decimal(a) for a in amounts]
    idx = [
        i for i, v in enumerate(parsed)
        if v is not None and "outstanding" not in (labels[i] or "").casefold()
    ]
    if not idx:
        return amounts
    vals = [abs(parsed[i]) for i in idx]

    for excluded_options in ([None], range(len(vals))):
        solutions: list[list[Decimal]] = []
        for ex in excluded_options:
            for signs in product((1, -1), repeat=len(vals) - (ex is not None)):
                it = iter(signs)
                signed = [-v if k == ex else next(it) * v for k, v in enumerate(vals)]
                if sum((s for k, s in enumerate(signed) if k != ex), Decimal("0")) == target:
                    solutions.append(signed)
                    if len(solutions) > 1:
                        return amounts  # ambiguous
        if solutions:
            out = list(amounts)
            for i, s in zip(idx, solutions[0]):
                out[i] = s
            return out

    return amounts
