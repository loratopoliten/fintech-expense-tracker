"""Financial Health Score engine — adapted from CapitalPyre CRS scorer."""

from typing import List
from dataclasses import dataclass


@dataclass
class TransactionSummary:
    total_income:         float
    total_expenses:       float
    months_active:        int
    categories:           List[str]
    avg_monthly_income:   float
    avg_monthly_expense:  float
    has_savings:          bool
    savings_rate:         float
    budget_adherence:     float
    expense_variance:     float
    emergency_fund_months: float


def score_income_stability(s: TransactionSummary) -> float:
    score = 0.0
    if s.avg_monthly_income > 0:  score += 10
    if s.months_active >= 3:      score += 5
    if s.months_active >= 6:      score += 5
    if s.expense_variance < 0.2:  score += 5
    return min(score, 25.0)


def score_savings_health(s: TransactionSummary) -> float:
    rate = s.savings_rate
    if rate >= 0.20:   return 25.0
    if rate >= 0.10:   return 18.0
    if rate >= 0.05:   return 10.0
    if rate >= 0.01:   return 5.0
    return 0.0


def score_budget_discipline(s: TransactionSummary) -> float:
    a = s.budget_adherence
    if a >= 0.9:  return 20.0
    if a >= 0.7:  return 14.0
    if a >= 0.5:  return 8.0
    if a > 0:     return 3.0
    return 2.0   # partial credit for using the app


def score_emergency_fund(s: TransactionSummary) -> float:
    m = s.emergency_fund_months
    if m >= 6:  return 15.0
    if m >= 3:  return 10.0
    if m >= 1:  return 5.0
    if m > 0:   return 2.0
    return 0.0


def score_spending_diversity(s: TransactionSummary) -> float:
    score = 0.0
    cats = len(set(s.categories))
    if cats >= 5:    score += 10
    elif cats >= 3:  score += 6
    elif cats >= 1:  score += 3
    if any(c.lower() in ("savings", "investment", "investments")
           for c in s.categories):
        score += 5
    return min(score, 15.0)


def get_band(score: float) -> str:
    if score >= 75: return "excellent"
    if score >= 55: return "good"
    if score >= 35: return "fair"
    return "needs_work"


def generate_tips(breakdown: dict, s: TransactionSummary) -> List[str]:
    tips = []
    if breakdown["income_stability"]  < 15:
        tips.append("Track income for at least 3 months to build a stability picture.")
    if breakdown["savings_health"]    < 15:
        tips.append(f"Your savings rate is {s.savings_rate*100:.0f}%. Aim for at least 10%.")
    if breakdown["budget_discipline"] < 10:
        tips.append("Set monthly budgets per category — it directly boosts your score.")
    if breakdown["emergency_fund"]    < 10:
        tips.append(f"You have {s.emergency_fund_months:.1f} months of emergency cover. Target: 3–6 months.")
    if breakdown["spending_diversity"] < 10:
        tips.append("Add a 'Savings' or 'Investment' category to your transactions.")
    if not tips:
        tips.append("Outstanding! Keep tracking consistently to maintain your score.")
    return tips


def compute_score(s: TransactionSummary) -> dict:
    breakdown = {
        "income_stability":   score_income_stability(s),
        "savings_health":     score_savings_health(s),
        "budget_discipline":  score_budget_discipline(s),
        "emergency_fund":     score_emergency_fund(s),
        "spending_diversity": score_spending_diversity(s),
    }
    total = round(sum(breakdown.values()), 2)
    return {
        "score":     total,
        "breakdown": breakdown,
        "band":      get_band(total),
        "tips":      generate_tips(breakdown, s),
    }


def build_summary_from_db(rows: list, budget_rows: list) -> TransactionSummary:
    income   = sum(r["amount"] for r in rows if r["type"] == "income")
    expenses = sum(r["amount"] for r in rows if r["type"] == "expense")
    months   = len(set(str(r["date"])[:7] for r in rows)) or 1
    cats     = [r["category"] for r in rows if r["type"] == "expense"]

    avg_income  = income / months
    avg_expense = expenses / months
    savings_rate = max((income - expenses) / income, 0.0) if income > 0 else 0.0

    # Budget adherence
    if budget_rows:
        hits = sum(
            1 for b in budget_rows
            if sum(r["amount"] for r in rows
                   if r["type"] == "expense"
                   and r["category"].lower() == b["category"].lower()
                   and str(r["date"])[:7] == b["month"]) <= b["limit_amt"]
        )
        adherence = hits / len(budget_rows)
    else:
        adherence = 0.0

    # Expense variance by month
    monthly_exp: dict = {}
    for r in rows:
        if r["type"] == "expense":
            m = str(r["date"])[:7]
            monthly_exp[m] = monthly_exp.get(m, 0) + r["amount"]

    if len(monthly_exp) >= 2:
        vals = list(monthly_exp.values())
        mean = sum(vals) / len(vals)
        std  = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
        exp_variance = std / mean if mean else 0.0
    else:
        exp_variance = 0.0

    net_savings      = max(income - expenses, 0)
    emergency_months = net_savings / avg_expense if avg_expense > 0 else 0.0

    return TransactionSummary(
        total_income=income, total_expenses=expenses,
        months_active=months, categories=cats,
        avg_monthly_income=avg_income, avg_monthly_expense=avg_expense,
        has_savings=income > expenses, savings_rate=savings_rate,
        budget_adherence=adherence, expense_variance=exp_variance,
        emergency_fund_months=emergency_months,
    )
