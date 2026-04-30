"""Transaction routes — CRUD + budgets + CSV export + date range filter."""

import csv
import io
from fastapi import APIRouter, Request, Form, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from datetime import date, datetime
from typing import Optional
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

P = "%s" if USE_POSTGRES else "?"


def _parse_date(value: str) -> str:
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError("date must be YYYY-MM-DD or DD/MM/YYYY")


def _clean_category(value: str) -> str:
    category = (value or "").strip()
    return category or "Other"


@router.get("", response_class=HTMLResponse)
async def transactions_page(
    request: Request,
    user=Depends(get_current_user),
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    type_filter: Optional[str] = Query(None),
):
    with db_cursor() as cur:
        query  = f"SELECT * FROM transactions WHERE user_id={P}"
        params = [user["sub"]]

        if date_from:
            query += f" AND date >= {P}"; params.append(date_from)
        if date_to:
            query += f" AND date <= {P}"; params.append(date_to)
        if type_filter and type_filter in ("income", "expense"):
            query += f" AND type = {P}"; params.append(type_filter)

        query += " ORDER BY date DESC, created_at DESC LIMIT 500"
        cur.execute(query, params)
        txns = [dict(r) for r in cur.fetchall()]

    # Totals for filtered set
    filtered_income   = sum(float(r["amount"]) for r in txns if r["type"] == "income")
    filtered_expenses = sum(float(r["amount"]) for r in txns if r["type"] == "expense")

    return templates.TemplateResponse("transactions/list.html", {
        "request": request, "user": user, "transactions": txns,
        "expense_categories": EXPENSE_CATEGORIES,
        "income_categories":  INCOME_CATEGORIES,
        "date_from":     date_from or "",
        "date_to":       date_to   or "",
        "type_filter":   type_filter or "",
        "filtered_income":   round(filtered_income, 2),
        "filtered_expenses": round(filtered_expenses, 2),
        "filtered_balance":  round(filtered_income - filtered_expenses, 2),
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
    try:
        date_val = _parse_date(date_val)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    category = _clean_category(category)

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


# ── CSV Export ────────────────────────────────────────────

@router.get("/export/csv")
async def export_csv(
    user=Depends(get_current_user),
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    type_filter: Optional[str] = Query(None),
):
    category = _clean_category(category)
    if limit_amt <= 0:
        raise HTTPException(400, "Budget limit must be positive")
    try:
        datetime.strptime(f"{month}-01", "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(400, "Month must be YYYY-MM") from exc

    with db_cursor() as cur:
        query  = f"SELECT date, type, category, description, amount FROM transactions WHERE user_id={P}"
        params = [user["sub"]]
        if date_from:
            query += f" AND date >= {P}"; params.append(date_from)
        if date_to:
            query += f" AND date <= {P}"; params.append(date_to)
        if type_filter and type_filter in ("income", "expense"):
            query += f" AND type = {P}"; params.append(type_filter)
        query += " ORDER BY date DESC"
        cur.execute(query, params)
        rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Type", "Category", "Description", "Amount (BWP)"])
    for r in rows:
        writer.writerow([r["date"], r["type"], r["category"], r["description"] or "", f"{float(r['amount']):.2f}"])

    output.seek(0)
    filename = f"fintrack-transactions-{date.today()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ── Budgets ───────────────────────────────────────────────

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


# ── API summary (for charts) ──────────────────────────────

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
