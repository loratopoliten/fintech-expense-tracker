from datetime import date
from typing import Optional

from app.database import USE_POSTGRES, db_cursor

P = "%s" if USE_POSTGRES else "?"


class GoalService:
    @staticmethod
    def list_goals(user_id: int) -> list[dict]:
        with db_cursor() as cur:
            cur.execute(f"SELECT * FROM savings_goals WHERE user_id={P} ORDER BY created_at DESC", (user_id,))
            goals = [dict(row) for row in cur.fetchall()]
        for goal in goals:
            target = float(goal["target_amt"])
            saved = float(goal["saved_amt"])
            goal["pct"] = round(min((saved / target) * 100, 100), 1) if target else 0
            goal["remaining"] = round(max(target - saved, 0), 2)
        return goals

    @staticmethod
    def add_goal(user_id: int, name: str, target_amt: float,
                 saved_amt: float = 0, due_date: Optional[str] = None) -> None:
        if target_amt <= 0:
            raise ValueError("Goal target must be positive")
        if saved_amt < 0:
            raise ValueError("Saved amount cannot be negative")
        if due_date:
            date.fromisoformat(due_date)
        with db_cursor() as cur:
            cur.execute(
                f"INSERT INTO savings_goals (user_id,name,target_amt,saved_amt,due_date) VALUES ({P},{P},{P},{P},{P})",
                (user_id, name.strip(), target_amt, saved_amt, due_date or None),
            )

    @staticmethod
    def update_saved(user_id: int, goal_id: int, saved_amt: float) -> None:
        if saved_amt < 0:
            raise ValueError("Saved amount cannot be negative")
        with db_cursor() as cur:
            cur.execute(f"UPDATE savings_goals SET saved_amt={P} WHERE id={P} AND user_id={P}", (saved_amt, goal_id, user_id))

    @staticmethod
    def delete_goal(user_id: int, goal_id: int) -> None:
        with db_cursor() as cur:
            cur.execute(f"DELETE FROM savings_goals WHERE id={P} AND user_id={P}", (goal_id, user_id))

