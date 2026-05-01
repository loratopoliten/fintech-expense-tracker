from datetime import date

import pytest

from app.schemas.finance import TransactionCreate
from app.services.recurring_service import add_month
from app.services.transaction_service import TransactionService, parse_transaction_date


def test_parse_transaction_date_accepts_iso_and_botswana_style():
    assert parse_transaction_date("2026-05-01") == "2026-05-01"
    assert parse_transaction_date("01/05/2026") == "2026-05-01"


def test_parse_transaction_date_rejects_unknown_format():
    with pytest.raises(ValueError):
        parse_transaction_date("05-01-2026")


def test_csv_export_includes_tags():
    rows = [{
        "date": "2026-05-01",
        "type": "expense",
        "category": "WiFi",
        "description": "Monthly internet",
        "tags": "home",
        "amount": 499.99,
    }]
    csv_text = TransactionService.to_csv(rows)
    assert "Tags" in csv_text
    assert "home" in csv_text


def test_add_month_clamps_end_of_month():
    assert add_month(date(2026, 1, 31)) == date(2026, 2, 28)


def test_transaction_schema_requires_positive_amount():
    with pytest.raises(Exception):
        TransactionCreate(
            type="expense",
            amount=0,
            category="Food",
            date=date(2026, 5, 1),
        )

