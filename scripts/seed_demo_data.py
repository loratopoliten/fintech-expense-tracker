"""Seed a local SQLite database with sample FinTrack data."""

from datetime import date

from app.database import init_db
from app.schemas.finance import TransactionCreate
from app.services.transaction_service import TransactionService


def main():
    init_db()
    user_id = 1
    samples = [
        TransactionCreate(type="income", amount=2500, category="Allowance", description="Monthly allowance", tags="school", date=date.today()),
        TransactionCreate(type="expense", amount=450, category="WiFi", description="Home internet", tags="utilities", date=date.today()),
        TransactionCreate(type="expense", amount=650, category="Rent", description="Shared rent", tags="housing", date=date.today()),
    ]
    for sample in samples:
        TransactionService.add_transaction(user_id, sample)
    print("Seeded demo transactions for user_id=1")


if __name__ == "__main__":
    main()
