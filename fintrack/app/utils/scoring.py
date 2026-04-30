"""
Financial Health Score Engine
Adapted from CapitalPyre's CRS scoring microservice — repurposed for personal finance.
Scores users 0–100 across 5 dimensions.
"""

from typing import List, Dict, Tuple
from dataclasses import dataclass
import json


@dataclass
class TransactionSummary:
    total_income:    float
    total_expenses:  float
    months_active:   int
    categories:      List[str]
    avg_monthly_income:   float
    avg_monthly_expense:  float
    has_savings:     bool
    savings_rate:    float          # 0.0 – 1.0
    budget_adherence: float         # 0.0 – 1.0  (fraction of budget categories under limit)
    expense_variance: float         # lower = more consistent = better
    emergency_fund_months: float    # months of expenses covered


# ── Scoring functions (max pts shown) ─────────────────────

def score_income_stability(summary: TransactionSummary) -> float:
    """Max 25 pts — Is income consistent and growing?"""
    score = 0.0
    if summary.avg_monthly_income > 0:
        score += 10
    if summary.months_active >= 3:
        score += 5
    if summary.months_active >= 6:
        score += 5
    # Low expense variance relative to income = stable lifestyle
    if summary.expense_variance < 0.2:
        score += 5
    return min(score, 25.0)


def score_savings_health(summary: TransactionSummary) -> float:
    """Max 25 pts — Are they saving?"""
    score = 0.0
    rate = summary.savings_rate
    if rate >= 0.20:    score += 25
    elif rate >= 0.10:  score += 18
    elif rate >= 0.05:  score += 10
    elif rate >= 0.01:  score += 5
    return min(score, 25.0)


def score_budget_discipline(summary: TransactionSummary) -> float:
    """Max 20 pts — Do they stick to budgets?"""
    score = 0.0
    adherence = summary.budget_adherence
    if adherence >= 0.9:   score += 20
    elif adherence >= 0.7: score += 14
    elif adherence >= 0.5: score += 8
    elif adherence > 0:    score += 3
    else:
        # No budgets set — partial credit for being in the app
        score += 2
    return min(score, 20.0)


def score_emergency_fund(summary: TransactionSummary) -> float:
    """Max 15 pts — Emergency fund coverage."""
    score = 0.0
    months = summary.emergency_fund_months
    if months >= 6:    score += 15
    elif months >= 3:  score += 10
    elif months >= 1:  score += 5
    elif months > 0:   score += 2
    return min(score, 15.0)


def score_spending_diversity(summary: TransactionSummary) -> float:
    """Max 15 pts — Healthy spending across categories (not over-concentrated)."""
    score = 0.0
    cats = len(set(summary.categories))
    if cats >= 5:    score += 10
    elif cats >= 3:  score += 6
    elif cats >= 1:  score += 3
    # Bonus for having 'savings' or 'investment' category
    if any(c.lower() in ("savings", "investment", "investments") for c in summary.categories):
        score += 5
    return min(score, 15.0)


def get_band(score: float) -> str:
    if score >= 75: return "excellent"
    if score >= 55: return "good"
    if score >= 35: return "fair"
    return "needs_work"


def generate_tips(breakdown: dict, summary: TransactionSummary) -> List[str]:
    tips = []
    if breakdown["income_stability"] < 15:
        tips.append("Track income for at least 3 months to build a stability picture.")
    if breakdown["savings_health"] < 15:
        tips.append(f"Your savings rate is {summary.savings_rate*100:.0f}%. Aim for at least 10%.")
    if breakdown["budget_discipline"] < 10:
        tips.append("Set monthly budgets per category to earn discipline points.")
    if breakdown["emergency_fund"] < 10:
        tips.append(f"You have {summary.emergency_fund_months:.1f} months of emergency cover. Target: 3–6 months.")
    if breakdown["spending_diversity"] < 10:
        tips.append("Add an 'Investment' or 'Savings' category to your transactions.")
    if not tips:
        tips.append("Outstanding! Keep tracking and stay consistent.")
    return tips


def compute_score(summary: TransactionSummary) -> dict:
    income_stability  = score_income_stability(summary)
    savings_health    = score_savings_health(summary)
    budget_discipline = score_budget_discipline(summary)
    emergency_fund    = score_emergency_fund(summary)
    spending_diversity = score_spending_diversity(summary)

    total = round(income_stability + savings_health + budget_discipline + emergency_fund + spending_diversity, 2)

    breakdown = {
        "income_stability":   income_stability,
        "savings_health":     savings_health,
        "budget_discipline":  budget_discipline,
        "emergency_fund":     emergency_fund,
        "spending_diversity": spending_diversity,
    }

    return {
        "score":     total,
        "breakdown": breakdown,
        "band":      get_band(total),
        "tips":      generate_tips(breakdown, summary),
    }


def build_summary_from_db(rows: List[dict], budget_rows: List[dict]) -> TransactionSummary:
    """Build a TransactionSummary from raw DB transaction and budget rows."""
    income   = sum(r["amount"] for r in rows if r["type"] == "income")
    expenses = sum(r["amount"] for r in rows if r["type"] == "expense")
    months   = len(set(str(r["date"])[:7] for r in rows)) or 1
    cats     = [r["category"] for r in rows if r["type"] == "expense"]

    avg_income  = income / months
    avg_expense = expenses / months
    savings_rate = (income - expenses) / income if income > 0 else 0.0

    # Budget adherence: fraction of (category, month) pairs under limit
    if budget_rows:
        hits = 0
        for b in budget_rows:
            spent = sum(
                r["amount"] for r in rows
                if r["type"] == "expense"
                and r["category"].lower() == b["category"].lower()
                and str(r["date"])[:7] == b["month"]
            )
            if spent <= b["limit_amt"]:
                hits += 1
        adherence = hits / len(budget_rows)
    else:
        adherence = 0.0

    # Expense variance (coefficient of variation by month)
    monthly_exp = {}
    for r in rows:
        if r["type"] == "expense":
            m = str(r["date"])[:7]
            monthly_exp[m] = monthly_exp.get(m, 0) + r["amount"]
    if len(monthly_exp) >= 2:
        vals = list(monthly_exp.values())
        mean = sum(vals) / len(vals)
        variance = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
        exp_variance = variance / mean if mean else 0
    else:
        exp_variance = 0.0

    net_savings      = max(income - expenses, 0)
    emergency_months = net_savings / avg_expense if avg_expense > 0 else 0

    return TransactionSummary(
        total_income=income,
        total_expenses=expenses,
        months_active=months,
        categories=cats,
        avg_monthly_income=avg_income,
        avg_monthly_expense=avg_expense,
        has_savings=income > expenses,
        savings_rate=max(savings_rate, 0),
        budget_adherence=adherence,
        expense_variance=exp_variance,
        emergency_fund_months=emergency_months,
    )
