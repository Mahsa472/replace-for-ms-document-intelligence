"""Pydantic schema for a reinsurance treaty balance statement (statement of account).

The target CSV is always the same, so there is ONE schema. It mirrors the real
structure of the page: a statement has header fields plus one OR MORE sections,
and each section has its own title, currency, rows and balance.

Keeping the sections nested (rather than a flat list of rows) means:
- the main class can be computed per section as  line_of_business + section title.
- reconciliation runs per section (each section has its own balance).
- a second section in another currency is handled naturally.
The flattening of sections -> CSV rows is done in to_csv.py, not here.

Dates are ISO (YYYY-MM-DD) in the schema; any other display format is applied
at export time.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import AfterValidator, BaseModel, Field, model_validator

# Signed amount, always rounded to 2 decimals (CR -> positive, DR -> negative).
Money = Annotated[Decimal, AfterValidator(lambda v: v.quantize(Decimal("0.01")))]

_MONEY_FORMAT = (
    "SIGNED (CR +, DR -). English decimal format with exactly two decimals, "
    "no thousands separator (e.g. 1321422.90). If the source uses commas as "
    "decimal separators, convert to dot."
)


class Party(BaseModel):
    """A named entity on the statement."""

    name: str = Field(description="Full legal name exactly as printed.")
    reference: Optional[str] = Field(
        default=None, description="Any account / partner number printed with the name."
    )


class StatementPeriod(BaseModel):
    """The two date ranges on the statement, as YYYY-MM-DD.

    e.g. '30/Jun/2026' -> '2026-06-30', '01/01/2025' -> '2025-01-01'.
    """

    accounting_start: Optional[date] = Field(
        default=None,
        description=(
            "Start date of the accounting period line (first line after the title). "
            "Null if only a single date is given (e.g. 'as at ...')."
        ),
    )
    accounting_end: Optional[date] = Field(
        default=None,
        description=(
            "End date of the accounting period line (first line after the title). "
            "If the line gives a single date ('as at <date>'), use that date here."
        ),
    )
    coverage_start: Optional[date] = Field(
        default=None, description="Start of the 'Period:' line in the reinsured block."
    )
    coverage_end: Optional[date] = Field(
        default=None, description="End of the 'Period:' line in the reinsured block."
    )


class StatementRow(BaseModel):
    """One row of a section.

    If a section has only one value column, put that value in amount_share.
    """

    category: str = Field(
        description="Normalised label: 'Premium', 'Tax', 'Commission', 'Paid Claims', 'Brokerage', 'Outstanding'."
    )
    printed_label: str = Field(description="Label exactly as printed, e.g. 'Premium Tax at 1%'.")
    amount_total: Optional[Money] = Field(
        default=None,
        description="Value in the '100% Amounts' column (not every layout has it). " + _MONEY_FORMAT,
    )
    amount_share: Optional[Money] = Field(
        default=None,
        description="Value in the 'Your Share' column, or the only value column if there is just one. "
        + _MONEY_FORMAT,
    )

    @model_validator(mode="after")
    def _at_least_one_amount(self) -> "StatementRow":
        if self.amount_total is None and self.amount_share is None:
            raise ValueError(f"Row '{self.printed_label}' has no amount in any column")
        return self


class StatementSection(BaseModel):
    """One balance table / section. A statement may contain several of these."""

    title: str = Field(description="The heading directly above this section, e.g. 'Section A'.")
    currency: str = Field(description="Currency of this section's amounts (label above it), e.g. 'USD'.")
    rows: list[StatementRow] = Field(
        description="Every row of this section, including 'Outstanding' (0 if 'Not Advised')."
    )
    balance: Optional[Money] = Field(
        default=None,
        description=(
            "This section's 'Due to you' or 'Due from you' amount in the Your Share column. "
            "'Due to you' -> positive, 'Due from you' -> negative. " + _MONEY_FORMAT
        ),
    )


class AccountStatement(BaseModel):
    """One treaty balance statement. The single output_type."""

    broker_name: Optional[str] = Field(default=None, description="Broker name in the header, e.g. 'Broker 1'.")
    statement_date: Optional[date] = Field(
        default=None, description="The 'Date' field in the header, e.g. '29-Jul-2026' -> 2026-07-29."
    )

    cedent: Party = Field(description="Company on the 'Reinsured:' line.")
    treaty_name: Optional[str] = Field(
        default=None, description="Value of the 'Interest:' line, e.g. 'Property Quota Share'."
    )
    line_of_business: Optional[str] = Field(
        default=None,
        description="Value of the 'Type:' line, e.g. 'Non Marine'. Combined with each section title to form the main class.",
    )

    contract_reference: Optional[str] = Field(
        default=None, description="'Risk Reference' in the header, e.g. 'RR-0001-2026'."
    )
    document_reference: Optional[str] = Field(
        default=None, description="'Transaction Ref.' in the header, e.g. 'TX-123456'."
    )
    account_id: Optional[str] = Field(
        default=None, description="'Account Number' in the header, e.g. 'ACC-0001'."
    )
    share_percent: Optional[Decimal] = Field(
        default=None,
        description="Share from the 'Your Share X%' column header: X as a number, not a fraction (3% -> 3).",
    )

    period: StatementPeriod = Field(default_factory=StatementPeriod)
    sections: list[StatementSection] = Field(
        description="Every balance section on the statement (usually one, sometimes more)."
    )
