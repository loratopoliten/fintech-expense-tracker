"""Dashboard route — main overview page."""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import date
from app.database import db_cursor
from app.utils.auth import get_current_user
from app.utils.scoring import build_summary_from_db, compute_score

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user=Depends(get_current_user)):
    uid = user["sub"]
    current_month = str(date.today())[:7]

    with db_cursor() as cur:
        cur.execute("SELECT * FROM transactions WHERE user_id=?", (uid,))
        all_txns = [dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT * FROM transactions WHERE user_id=? AND date LIKE ? ORDER BY date DESC LIMIT 10",
            (uid, f"{current_month}%")
        )
        recent = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM budgets WHERE user_id=? AND month=?", (uid, current_month))
        budgets = [dict(r) for r in cur.fetchall()]

    income_month   = sum(r["amount"] for r in all_txns if r["type"] == "income" and str(r["date"]).startswith(current_month))
    expense_month  = sum(r["amount"] for r in all_txns if r["type"] == "expense" and str(r["date"]).startswith(current_month))
    total_income   = sum(r["amount"] for r in all_txns if r["type"] == "income")
    total_expenses = sum(r["amount"] for r in all_txns if r["type"] == "expense")

    savings_rate = round((income_month - expense_month) / income_month * 100, 1) if income_month > 0 else 0.0

    # Top expense category this month
    cat_spend: dict[str, float] = {}
    for r in all_txns:
        if r["type"] == "expense" and str(r["date"]).startswith(current_month):
            cat_spend[r["category"]] = cat_spend.get(r["category"], 0) + r["amount"]
    top_category = max(cat_spend, key=cat_spend.get) if cat_spend else None

    # Quick score
    if all_txns:
        summary = build_summary_from_db(all_txns, budgets)
        score_result = compute_score(summary)
        fhs_score = round(score_result["score"])
        fhs_band  = score_result["band"]
    else:
        fhs_score = 0
        fhs_band  = "needs_work"

    return templates.TemplateResponse("dashboard/index.html", {
        "request": request,
        "user": user,
        "income_month":   round(income_month, 2),
        "expense_month":  round(expense_month, 2),
        "balance_month":  round(income_month - expense_month, 2),
        "total_income":   round(total_income, 2),
        "total_expenses": round(total_expenses, 2),
        "net_balance":    round(total_income - total_expenses, 2),
        "savings_rate":   savings_rate,
        "top_category":   top_category,
        "recent":         recent,
        "fhs_score":      fhs_score,
        "fhs_band":       fhs_band,
        "current_month":  current_month,
        "txn_count":      len(all_txns),
    })
