from calendar import monthrange
from datetime import date
from typing import Optional

from app.database import USE_POSTGRES, db_cursor
from app.schemas.finance import TransactionCreate
from app.services.transaction_service import clean_category, TransactionService

P = "%s" if USE_POSTGRES else "?"


def add_month(value: date) -> date:
    month = value.month + 1
    year = value.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


class RecurringService:
    @staticmethod
    def list_recurring(user_id: int) -> list[dict]:
        with db_cursor() as cur:
            active_clause = "active=TRUE" if USE_POSTGRES else "active=1"
            cur.execute(f"SELECT * FROM recurring_transactions WHERE user_id={P} AND {active_clause} ORDER BY next_date ASC", (user_id,))
            return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def add_recurring(user_id: int, txn_type: str, amount: float, category: str,
                      description: str, tags: str, next_date: str) -> None:
        if txn_type not in ("income", "expense"):
            raise ValueError("Invalid type")
        if amount <= 0:
            raise ValueError("Amount must be positive")
        date.fromisoformat(next_date)
        with db_cursor() as cur:
            cur.execute(
                f"""INSERT INTO recurring_transactions
                    (user_id,type,amount,category,description,tags,frequency,next_date)
                    VALUES ({P},{P},{P},{P},{P},{P},{P},{P})""",
                (user_id, txn_type, amount, clean_category(category), description, tags, "monthly", next_date),
            )

    @staticmethod
    def apply_due(user_id: int, today: Optional[date] = None) -> int:
        today = today or date.today()
        created = 0
        with db_cursor() as cur:
            active_clause = "active=TRUE" if USE_POSTGRES else "active=1"
            cur.execute(
                f"SELECT * FROM recurring_transactions WHERE user_id={P} AND {active_clause} AND next_date <= {P}",
                (user_id, today.isoformat()),
            )
            due_rows = [dict(row) for row in cur.fetchall()]
        for row in due_rows:
            payload = TransactionCreate(
                type=row["type"],
                amount=float(row["amount"]),
                category=row["category"],
                description=row.get("description") or "",
                tags=row.get("tags") or "",
                is_recurring=True,
                parent_transaction_id=None,
                date=date.fromisoformat(str(row["next_date"])),
            )
            TransactionService.add_transaction(user_id, payload)
            next_date = add_month(date.fromisoformat(str(row["next_date"])))
            with db_cursor() as cur:
                cur.execute(f"UPDATE recurring_transactions SET next_date={P} WHERE id={P} AND user_id={P}", (next_date.isoformat(), row["id"], user_id))
            created += 1
        return created

    @staticmethod
    def delete_recurring(user_id: int, recurring_id: int) -> None:
        with db_cursor() as cur:
            cur.execute(f"UPDATE recurring_transactions SET active=0 WHERE id={P} AND user_id={P}", (recurring_id, user_id))
