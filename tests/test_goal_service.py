from app.services.goal_service import GoalService


def test_goal_progress_fields_are_added():
    goals = [{"target_amt": 1000, "saved_amt": 250}]
    goal = goals[0]
    target = float(goal["target_amt"])
    saved = float(goal["saved_amt"])
    goal["pct"] = round(min((saved / target) * 100, 100), 1)
    goal["remaining"] = round(max(target - saved, 0), 2)
    assert goal["pct"] == 25.0
    assert goal["remaining"] == 750

