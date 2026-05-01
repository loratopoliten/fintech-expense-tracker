"""Transaction routes — CRUD + budgets + CSV export + date range filter."""

from fastapi import APIRouter, Request, Form, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse, StreamingResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from datetime import date, datetime
from typing import Optional
from app.database import db_cursor, USE_POSTGRES
from app.schemas.finance import TransactionCreate
from app.services.budget_service import BudgetService
from app.services.goal_service import GoalService
from app.services.recurring_service import RecurringService
from app.services.report_service import ReportService
from app.services.transaction_service import (
    EXPENSE_CATEGORIES,
    INCOME_CATEGORIES,
    TransactionService,
    clean_category as _clean_category,
    parse_transaction_date as _parse_date,
)
from app.utils.auth import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")

P = "%s" if USE_POSTGRES else "?"


@router.get("", response_class=HTMLResponse)
async def transactions_page(
    request: Request,
    user=Depends(get_current_user),
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    type_filter: Optional[str] = Query(None),
):
    txns = TransactionService.list_transactions(user["sub"], date_from, date_to, type_filter)
    recurring = RecurringService.list_recurring(user["sub"])

    totals = TransactionService.totals(txns)

    return templates.TemplateResponse("transactions/list.html", {
        "request": request, "user": user, "transactions": txns,
        "recurring": recurring,
        "expense_categories": EXPENSE_CATEGORIES,
        "income_categories":  INCOME_CATEGORIES,
        "date_from":     date_from or "",
        "date_to":       date_to   or "",
        "type_filter":   type_filter or "",
        "filtered_income":   totals["income"],
        "filtered_expenses": totals["expenses"],
        "filtered_balance":  totals["balance"],
    })


@router.post("/add")
async def add_transaction(
    request: Request, user=Depends(get_current_user),
    type: str = Form(...), amount: float = Form(...),
    category: str = Form(...), description: str = Form(""),
    date_val: str = Form(str(date.today())),
    tags: str = Form(""),
):
    if type not in ("income", "expense"):
        raise HTTPException(400, "Invalid type")
    if amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    try:
        date_val = _parse_date(date_val)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    payload = TransactionCreate(
        type=type,
        amount=amount,
        category=_clean_category(category),
        description=description,
        date=date.fromisoformat(date_val),
        tags=tags,
    )
    TransactionService.add_transaction(user["sub"], payload)
    return RedirectResponse("/transactions", status_code=303)


@router.post("/delete/{txn_id}")
async def delete_transaction(txn_id: int, user=Depends(get_current_user)):
    TransactionService.delete_transaction(user["sub"], txn_id)
    return RedirectResponse("/transactions", status_code=303)


# ── CSV Export ────────────────────────────────────────────

@router.get("/export/csv")
async def export_csv(
    user=Depends(get_current_user),
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    type_filter: Optional[str] = Query(None),
):
    rows = TransactionService.list_transactions(user["sub"], date_from, date_to, type_filter, 0)
    output = TransactionService.to_csv(rows)
    filename = f"fintrack-transactions-{date.today()}.csv"
    return StreamingResponse(
        iter([output]),
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
    try:
        BudgetService.upsert_budget(user["sub"], category, limit_amt, month)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse("/transactions/budgets", status_code=303)


# ── API summary (for charts) ──────────────────────────────

@router.get("/api/summary")
async def api_summary(user=Depends(get_current_user)):
    rows = TransactionService.list_transactions(user["sub"], limit=0)

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


@router.get("/api/monthly-report")
async def api_monthly_report(month: Optional[str] = Query(None), user=Depends(get_current_user)):
    return JSONResponse(TransactionService.monthly_summary(user["sub"], month))


@router.get("/reports/monthly.txt")
async def monthly_report_text(month: Optional[str] = Query(None), user=Depends(get_current_user)):
    return PlainTextResponse(ReportService.monthly_digest_text(user["sub"], month))


@router.post("/recurring/add")
async def add_recurring(
    user=Depends(get_current_user),
    type: str = Form(...),
    amount: float = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    tags: str = Form(""),
    next_date: str = Form(...),
):
    try:
        RecurringService.add_recurring(user["sub"], type, amount, category, description, tags, next_date)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse("/transactions", status_code=303)


@router.post("/recurring/apply")
async def apply_recurring(user=Depends(get_current_user)):
    created = RecurringService.apply_due(user["sub"])
    return RedirectResponse(f"/transactions?recurring_created={created}", status_code=303)


@router.post("/recurring/delete/{recurring_id}")
async def delete_recurring(recurring_id: int, user=Depends(get_current_user)):
    RecurringService.delete_recurring(user["sub"], recurring_id)
    return RedirectResponse("/transactions", status_code=303)


@router.post("/split/add")
async def add_split_transaction(
    user=Depends(get_current_user),
    type: str = Form(...),
    date_val: str = Form(str(date.today())),
    description: str = Form(""),
    tags: str = Form(""),
    category_1: str = Form(...),
    amount_1: float = Form(...),
    category_2: str = Form(...),
    amount_2: float = Form(...),
):
    try:
        TransactionService.add_split_transaction(
            user["sub"], type, date_val, description, tags,
            [(category_1, amount_1), (category_2, amount_2)],
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse("/transactions", status_code=303)


@router.get("/goals", response_class=HTMLResponse)
async def goals_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("transactions/goals.html", {
        "request": request,
        "user": user,
        "goals": GoalService.list_goals(user["sub"]),
    })


@router.post("/goals/add")
async def add_goal(
    user=Depends(get_current_user),
    name: str = Form(...),
    target_amt: float = Form(...),
    saved_amt: float = Form(0),
    due_date: str = Form(""),
):
    try:
        GoalService.add_goal(user["sub"], name, target_amt, saved_amt, due_date or None)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse("/transactions/goals", status_code=303)


@router.post("/goals/update/{goal_id}")
async def update_goal(goal_id: int, user=Depends(get_current_user), saved_amt: float = Form(...)):
    try:
        GoalService.update_saved(user["sub"], goal_id, saved_amt)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse("/transactions/goals", status_code=303)


@router.post("/goals/delete/{goal_id}")
async def delete_goal(goal_id: int, user=Depends(get_current_user)):
    GoalService.delete_goal(user["sub"], goal_id)
    return RedirectResponse("/transactions/goals", status_code=303)
