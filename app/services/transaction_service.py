import csv
import io
from datetime import date, datetime
from typing import Iterable, Optional

from app.database import USE_POSTGRES, db_cursor
from app.schemas.finance import TransactionCreate

P = "%s" if USE_POSTGRES else "?"


INCOME_CATEGORIES = [
    "Allowance", "Side Hustle", "Salary", "Freelance",
    "Business", "Investment Returns", "Gift", "Other",
]

EXPENSE_CATEGORIES = [
    "Rent", "Food", "Transport", "WiFi", "UVK", "Utilities",
    "Housing", "Healthcare", "Education",
    "Entertainment", "Clothing", "Insurance",
    "Savings", "Investment", "Debt Repayment", "Other",
]


def parse_transaction_date(value: str) -> str:
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError("date must be YYYY-MM-DD or DD/MM/YYYY")


def clean_category(value: str) -> str:
    category = (value or "").strip()
    return category or "Other"


class TransactionService:
    @staticmethod
    def list_transactions(user_id: int, date_from: Optional[str] = None,
                          date_to: Optional[str] = None,
                          type_filter: Optional[str] = None,
                          limit: int = 500) -> list[dict]:
        with db_cursor() as cur:
            query = f"SELECT * FROM transactions WHERE user_id={P}"
            params = [user_id]
            if date_from:
                query += f" AND date >= {P}"
                params.append(date_from)
            if date_to:
                query += f" AND date <= {P}"
                params.append(date_to)
            if type_filter in ("income", "expense"):
                query += f" AND type = {P}"
                params.append(type_filter)
            query += " ORDER BY date DESC, created_at DESC"
            if limit:
                query += f" LIMIT {int(limit)}"
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def add_transaction(user_id: int, payload: TransactionCreate) -> int:
        with db_cursor() as cur:
            cur.execute(
                f"""INSERT INTO transactions
                    (user_id, type, amount, category, description, tags, is_recurring,
                     parent_transaction_id, date)
                    VALUES ({P},{P},{P},{P},{P},{P},{P},{P},{P})""",
                (
                    user_id, payload.type, payload.amount, clean_category(payload.category),
                    payload.description, payload.tags, int(payload.is_recurring),
                    payload.parent_transaction_id, payload.date.isoformat(),
                ),
            )
            return getattr(cur.cursor, "lastrowid", 0) or 0

    @staticmethod
    def add_split_transaction(user_id: int, txn_type: str, date_value: str,
                              description: str, tags: str,
                              splits: list[tuple[str, float]]) -> int:
        if txn_type not in ("income", "expense"):
            raise ValueError("Invalid type")
        clean_splits = [(clean_category(category), float(amount)) for category, amount in splits if float(amount) > 0]
        if len(clean_splits) < 2:
            raise ValueError("Split transactions need at least two positive category amounts")
        parent_amount = sum(amount for _, amount in clean_splits)
        parent = TransactionCreate(
            type=txn_type,
            amount=parent_amount,
            category="Split",
            description=description,
            tags=tags,
            date=date.fromisoformat(parse_transaction_date(date_value)),
        )
        parent_id = TransactionService.add_transaction(user_id, parent)
        for category, amount in clean_splits:
            child = TransactionCreate(
                type=txn_type,
                amount=amount,
                category=category,
                description=description,
                tags=tags,
                date=parent.date,
                parent_transaction_id=parent_id or None,
            )
            TransactionService.add_transaction(user_id, child)
        return parent_id

    @staticmethod
    def delete_transaction(user_id: int, transaction_id: int) -> None:
        with db_cursor() as cur:
            cur.execute(f"DELETE FROM transactions WHERE id={P} AND user_id={P}", (transaction_id, user_id))

    @staticmethod
    def totals(rows: Iterable[dict]) -> dict:
        rows = list(rows)
        income = sum(float(r["amount"]) for r in rows if r["type"] == "income")
        expenses = sum(float(r["amount"]) for r in rows if r["type"] == "expense")
        return {
            "income": round(income, 2),
            "expenses": round(expenses, 2),
            "balance": round(income - expenses, 2),
        }

    @staticmethod
    def to_csv(rows: Iterable[dict]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Type", "Category", "Description", "Tags", "Amount (BWP)"])
        for row in rows:
            writer.writerow([
                row["date"], row["type"], row["category"], row.get("description") or "",
                row.get("tags") or "", f"{float(row['amount']):.2f}",
            ])
        return output.getvalue()

    @staticmethod
    def monthly_summary(user_id: int, month: Optional[str] = None) -> dict:
        month = month or str(date.today())[:7]
        rows = TransactionService.list_transactions(user_id, month + "-01", month + "-31", None, 0)
        totals = TransactionService.totals(rows)
        return {"month": month, "transaction_count": len(rows), **totals}
