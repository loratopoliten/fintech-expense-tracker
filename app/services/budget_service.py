from datetime import datetime

from app.database import USE_POSTGRES, db_cursor
from app.services.transaction_service import clean_category

P = "%s" if USE_POSTGRES else "?"


class BudgetService:
    @staticmethod
    def validate_month(month: str) -> str:
        try:
            datetime.strptime(f"{month}-01", "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("Month must be YYYY-MM") from exc
        return month

    @staticmethod
    def upsert_budget(user_id: int, category: str, limit_amt: float, month: str) -> None:
        category = clean_category(category)
        if limit_amt <= 0:
            raise ValueError("Budget limit must be positive")
        month = BudgetService.validate_month(month)
        with db_cursor() as cur:
            if USE_POSTGRES:
                cur.execute(
                    f"""INSERT INTO budgets (user_id,category,limit_amt,month)
                        VALUES ({P},{P},{P},{P})
                        ON CONFLICT(user_id,category,month)
                        DO UPDATE SET limit_amt=EXCLUDED.limit_amt""",
                    (user_id, category, limit_amt, month),
                )
            else:
                cur.execute(
                    f"""INSERT INTO budgets (user_id,category,limit_amt,month)
                        VALUES ({P},{P},{P},{P})
                        ON CONFLICT(user_id,category,month)
                        DO UPDATE SET limit_amt=excluded.limit_amt""",
                    (user_id, category, limit_amt, month),
                )

