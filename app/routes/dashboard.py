from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import date
from app.database import db_cursor, USE_POSTGRES
from app.utils.auth import get_current_user, optional_user
from app.utils.scoring import build_summary_from_db, compute_score

router = APIRouter()
templates = Jinja2Templates(directory="templates")
P = "%s" if USE_POSTGRES else "?"


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user=Depends(get_current_user)):
    uid = user["sub"]
    current_month = str(date.today())[:7]

    with db_cursor() as cur:
        cur.execute(f"SELECT * FROM transactions WHERE user_id={P}", (uid,))
        all_txns = [dict(r) for r in cur.fetchall()]

        if USE_POSTGRES:
            cur.execute(
                f"SELECT * FROM transactions WHERE user_id={P} AND TO_CHAR(date,'YYYY-MM')={P} ORDER BY date DESC LIMIT 5",
                (uid, current_month))
        else:
            cur.execute(
                f"SELECT * FROM transactions WHERE user_id={P} AND date LIKE {P} ORDER BY date DESC LIMIT 5",
                (uid, f"{current_month}%"))
        recent = [dict(r) for r in cur.fetchall()]

        cur.execute(f"SELECT * FROM budgets WHERE user_id={P} AND month={P}", (uid, current_month))
        budgets = [dict(r) for r in cur.fetchall()]

    def month_total(t, typ):
        return sum(float(r["amount"]) for r in t
                   if r["type"] == typ and str(r["date"]).startswith(current_month))

    income_month  = month_total(all_txns, "income")
    expense_month = month_total(all_txns, "expense")
    total_income  = sum(float(r["amount"]) for r in all_txns if r["type"] == "income")
    total_expenses= sum(float(r["amount"]) for r in all_txns if r["type"] == "expense")

    fhs_score, fhs_band = 0, "needs_work"
    if all_txns:
        summary = build_summary_from_db(all_txns, budgets)
        result  = compute_score(summary)
        fhs_score = round(result["score"])
        fhs_band  = result["band"]

    return templates.TemplateResponse("dashboard/index.html", {
        "request": request, "user": user,
        "income_month":   round(income_month, 2),
        "expense_month":  round(expense_month, 2),
        "balance_month":  round(income_month - expense_month, 2),
        "total_income":   round(total_income, 2),
        "total_expenses": round(total_expenses, 2),
        "net_balance":    round(total_income - total_expenses, 2),
        "recent":         recent,
        "fhs_score":      fhs_score,
        "fhs_band":       fhs_band,
        "current_month":  current_month,
        "txn_count":      len(all_txns),
    })
