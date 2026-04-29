"""Transaction routes — CRUD + budgets. SQL uses ? placeholders (SQLite) or %s (Postgres)."""

from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import date
from app.database import db_cursor, USE_POSTGRES
from app.utils.auth import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")

EXPENSE_CATEGORIES = [
    "Housing", "Food", "Transport", "Healthcare", "Education",
    "Entertainment", "Clothing", "Utilities", "Insurance",
    "Savings", "Investment", "Debt Repayment", "Other",
]
INCOME_CATEGORIES = ["Salary", "Freelance", "Business", "Investment Returns", "Gift", "Other"]

P = "%s" if USE_POSTGRES else "?"   # placeholder character


@router.get("", response_class=HTMLResponse)
async def transactions_page(request: Request, user=Depends(get_current_user)):
    with db_cursor() as cur:
        cur.execute(
            f"SELECT * FROM transactions WHERE user_id={P} ORDER BY date DESC, created_at DESC LIMIT 200",
            (user["sub"],))
        txns = [dict(r) for r in cur.fetchall()]
    return templates.TemplateResponse("transactions/list.html", {
        "request": request, "user": user, "transactions": txns,
        "expense_categories": EXPENSE_CATEGORIES,
        "income_categories": INCOME_CATEGORIES,
    })


@router.post("/add")
async def add_transaction(
    request: Request, user=Depends(get_current_user),
    type: str = Form(...), amount: float = Form(...),
    category: str = Form(...), description: str = Form(""),
    date_val: str = Form(str(date.today())),
):
    if type not in ("income", "expense"):
        raise HTTPException(400, "Invalid type")
    if amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    with db_cursor() as cur:
        cur.execute(
            f"INSERT INTO transactions (user_id, type, amount, category, description, date) VALUES ({P},{P},{P},{P},{P},{P})",
            (user["sub"], type, amount, category, description, date_val))
    return RedirectResponse("/transactions", status_code=303)


@router.post("/delete/{txn_id}")
async def delete_transaction(txn_id: int, user=Depends(get_current_user)):
    with db_cursor() as cur:
        cur.execute(f"DELETE FROM transactions WHERE id={P} AND user_id={P}", (txn_id, user["sub"]))
    return RedirectResponse("/transactions", status_code=303)


@router.get("/budgets", response_class=HTMLResponse)
async def budgets_page(request: Request, user=Depends(get_current_user)):
    current_month = str(date.today())[:7]
    with db_cursor() as cur:
        cur.execute(f"SELECT * FROM budgets WHERE user_id={P} AND month={P}", (user["sub"], current_month))
        budgets = [dict(r) for r in cur.fetchall()]
        if USE_POSTGRES:
            cur.execute(
                f"SELECT category, SUM(amount) as spent FROM transactions WHERE user_id={P} AND type='expense' AND TO_CHAR(date,'YYYY-MM')={P} GROUP BY category",
                (user["sub"], current_month))
        else:
            cur.execute(
                f"SELECT category, SUM(amount) as spent FROM transactions WHERE user_id={P} AND type='expense' AND date LIKE {P} GROUP BY category",
                (user["sub"], f"{current_month}%"))
        spending = {r["category"]: float(r["spent"]) for r in cur.fetchall()}

    budgets_out = []
    for b in budgets:
        spent = spending.get(b["category"], 0)
        pct   = min((spent / float(b["limit_amt"])) * 100, 100) if b["limit_amt"] else 0
        budgets_out.append({**dict(b), "spent": spent, "pct": round(pct, 1)})

    return templates.TemplateResponse("transactions/budgets.html", {
        "request": request, "user": user,
        "budgets": budgets_out, "categories": EXPENSE_CATEGORIES,
        "current_month": current_month,
    })


@router.post("/budgets/set")
async def set_budget(
    user=Depends(get_current_user),
    category: str = Form(...), limit_amt: float = Form(...),
    month: str = Form(str(date.today())[:7]),
):
    with db_cursor() as cur:
        if USE_POSTGRES:
            cur.execute(
                f"INSERT INTO budgets (user_id,category,limit_amt,month) VALUES ({P},{P},{P},{P}) ON CONFLICT(user_id,category,month) DO UPDATE SET limit_amt=EXCLUDED.limit_amt",
                (user["sub"], category, limit_amt, month))
        else:
            cur.execute(
                f"INSERT INTO budgets (user_id,category,limit_amt,month) VALUES ({P},{P},{P},{P}) ON CONFLICT(user_id,category,month) DO UPDATE SET limit_amt=excluded.limit_amt",
                (user["sub"], category, limit_amt, month))
    return RedirectResponse("/transactions/budgets", status_code=303)


@router.get("/api/summary")
async def api_summary(user=Depends(get_current_user)):
    with db_cursor() as cur:
        cur.execute(f"SELECT * FROM transactions WHERE user_id={P}", (user["sub"],))
        rows = [dict(r) for r in cur.fetchall()]

    income   = sum(r["amount"] for r in rows if r["type"] == "income")
    expenses = sum(r["amount"] for r in rows if r["type"] == "expense")

    by_cat: dict = {}
    for r in rows:
        if r["type"] == "expense":
            by_cat[r["category"]] = by_cat.get(r["category"], 0) + float(r["amount"])

    by_month: dict = {}
    for r in rows:
        m = str(r["date"])[:7]
        if m not in by_month:
            by_month[m] = {"income": 0.0, "expense": 0.0}
        by_month[m][r["type"]] += float(r["amount"])

    return JSONResponse({
        "total_income":      round(float(income), 2),
        "total_expenses":    round(float(expenses), 2),
        "balance":           round(float(income - expenses), 2),
        "by_category":       {k: round(v, 2) for k, v in by_cat.items()},
        "by_month":          {k: {kk: round(vv, 2) for kk, vv in v.items()}
                              for k, v in sorted(by_month.items())},
        "transaction_count": len(rows),
    })
