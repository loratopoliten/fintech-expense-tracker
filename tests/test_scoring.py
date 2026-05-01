from app.utils.scoring import TransactionSummary, compute_score


def test_compute_score_rewards_savings_and_diversity():
    summary = TransactionSummary(
        total_income=10000,
        total_expenses=7000,
        months_active=6,
        categories=["Rent", "Food", "WiFi", "Savings", "Transport"],
        avg_monthly_income=1666.67,
        avg_monthly_expense=1166.67,
        has_savings=True,
        savings_rate=0.30,
        budget_adherence=1.0,
        expense_variance=0.1,
        emergency_fund_months=3,
    )
    result = compute_score(summary)
    assert result["score"] >= 75
    assert result["band"] == "excellent"

