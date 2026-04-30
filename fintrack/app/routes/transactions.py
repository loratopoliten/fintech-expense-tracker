"""Transaction routes — full CRUD for income/expense entries + budget management."""

import csv
import io
from fastapi import APIRouter, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from datetime import date, datetime
from app.database import db_cursor
from app.utils.auth import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")

EXPENSE_CATEGORIES = [
    "Rent", "Food", "Transport", "Utilities", "Clothing",
    "Healthcare", "Education", "Entertainment",
    "Insurance", "Savings", "Investment", "Debt Repayment", "Other"
]
INCOME_CATEGORIES = ["Allowance", "Side Hustle", "Salary", "Business", "Investment Returns", "Gift", "Other"]


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


# ── List & Add ───────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def transactions_page(request: Request, user=Depends(get_current_user)):
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM transactions WHERE user_id=? ORDER BY date DESC, created_at DESC LIMIT 100",
            (user["sub"],)
        )
        txns = [dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT DISTINCT category FROM transactions WHERE user_id=? AND type='income'",
            (user["sub"],)
        )
        used_income = [r["category"] for r in cur.fetchall()]

        cur.execute(
            "SELECT DISTINCT category FROM transactions WHERE user_id=? AND type='expense'",
            (user["sub"],)
        )
        used_expense = [r["category"] for r in cur.fetchall()]

    # User's own categories first, then standard defaults (deduped)
    income_suggestions  = list(dict.fromkeys(used_income  + INCOME_CATEGORIES))
    expense_suggestions = list(dict.fromkeys(used_expense + EXPENSE_CATEGORIES))

    return templates.TemplateResponse("transactions/list.html", {
        "request": request, "user": user, "transactions": txns,
        "income_categories":  income_suggestions,
        "expense_categories": expense_suggestions,
        "now": str(date.today()),
    })


@router.post("/add")
async def add_transaction(
    request: Request,
    user=Depends(get_current_user),
    type:        str   = Form(...),
    amount:      float = Form(...),
    category:    str   = Form(...),
    description: str   = Form(""),
    date_val:    str   = Form(str(date.today())),
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
            "INSERT INTO transactions (user_id, type, amount, category, description, date) VALUES (?,?,?,?,?,?)",
            (user["sub"], type, amount, category, description, date_val)
        )
    return RedirectResponse("/transactions", status_code=303)


@router.post("/delete/{txn_id}")
async def delete_transaction(txn_id: int, user=Depends(get_current_user)):
    with db_cursor() as cur:
        cur.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (txn_id, user["sub"]))
    return RedirectResponse("/transactions", status_code=303)


# ── CSV Export ───────────────────────────────────────────

@router.get("/export")
async def export_transactions(user=Depends(get_current_user)):
    with db_cursor() as cur:
        cur.execute(
            "SELECT date, type, category, amount, description FROM transactions WHERE user_id=? ORDER BY date ASC",
            (user["sub"],)
        )
        rows = [dict(r) for r in cur.fetchall()]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "type", "category", "amount", "description"])
    for r in rows:
        writer.writerow([r["date"], r["type"], r["category"], r["amount"], r["description"] or ""])

    filename = f"fintrack_{date.today()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── CSV Import ────────────────────────────────────────────

@router.post("/import")
async def import_transactions(
    user=Depends(get_current_user),
    file: UploadFile = File(...),
):
    content = await file.read()
    if not content:
        return RedirectResponse("/transactions?imported=0&skipped=0&errs=1", status_code=303)

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    imported = skipped = 0
    errors = []
    required = {"date", "type", "amount"}
    headers = {h.strip().lower() for h in (reader.fieldnames or [])}
    if not required.issubset(headers):
        return RedirectResponse("/transactions?imported=0&skipped=0&errs=1", status_code=303)

    with db_cursor() as cur:
        for i, row in enumerate(reader, 1):
            try:
                normalized = {(k or "").strip().lower(): v for k, v in row.items()}
                raw_date = _parse_date(normalized.get("date", ""))

                txn_type = normalized.get("type", "").strip().lower()
                if txn_type not in ("income", "expense"):
                    errors.append(f"Row {i}: unknown type '{txn_type}'")
                    continue

                raw_amount = normalized.get("amount", "").strip().lstrip("P").replace(",", "")
                amount = float(raw_amount)
                if amount <= 0:
                    errors.append(f"Row {i}: amount must be positive")
                    continue

                category = _clean_category(normalized.get("category", ""))
                description = (normalized.get("description", "") or "").strip()

                # Skip exact duplicates (same date, type, category, amount)
                cur.execute(
                    "SELECT 1 FROM transactions WHERE user_id=? AND date=? AND type=? AND category=? AND amount=?",
                    (user["sub"], raw_date, txn_type, category, amount),
                )
                if cur.fetchone():
                    skipped += 1
                    continue

                cur.execute(
                    "INSERT INTO transactions (user_id, type, amount, category, description, date) VALUES (?,?,?,?,?,?)",
                    (user["sub"], txn_type, amount, category, description, raw_date),
                )
                imported += 1
            except Exception as e:
                errors.append(f"Row {i}: {e}")

    return RedirectResponse(
        f"/transactions?imported={imported}&skipped={skipped}&errs={len(errors)}",
        status_code=303,
    )


# ── Budget management ────────────────────────────────────

@router.get("/budgets", response_class=HTMLResponse)
async def budgets_page(request: Request, user=Depends(get_current_user)):
    current_month = str(date.today())[:7]
    with db_cursor() as cur:
        cur.execute("SELECT * FROM budgets WHERE user_id=? AND month=?", (user["sub"], current_month))
        budgets = [dict(r) for r in cur.fetchall()]

        cur.execute(
            """SELECT category, SUM(amount) as spent FROM transactions
               WHERE user_id=? AND type='expense' AND date LIKE ?
               GROUP BY category""",
            (user["sub"], f"{current_month}%")
        )
        spending = {r["category"]: r["spent"] for r in cur.fetchall()}

        # All expense categories the user has ever used
        cur.execute(
            "SELECT DISTINCT category FROM transactions WHERE user_id=? AND type='expense'",
            (user["sub"],)
        )
        used_expense = [r["category"] for r in cur.fetchall()]

    budgets_with_spending = []
    for b in budgets:
        spent = spending.get(b["category"], 0)
        pct   = min((spent / b["limit_amt"]) * 100, 100) if b["limit_amt"] > 0 else 0
        budgets_with_spending.append({**b, "spent": spent, "pct": round(pct, 1)})

    # User's own categories first, then standard defaults (deduped)
    category_suggestions = list(dict.fromkeys(used_expense + EXPENSE_CATEGORIES))

    return templates.TemplateResponse("transactions/budgets.html", {
        "request": request, "user": user,
        "budgets": budgets_with_spending,
        "categories": category_suggestions,
        "current_month": current_month,
    })


@router.post("/budgets/set")
async def set_budget(
    user=Depends(get_current_user),
    category:  str   = Form(...),
    limit_amt: float = Form(...),
    month:     str   = Form(str(date.today())[:7]),
):
    category = _clean_category(category)
    if limit_amt <= 0:
        raise HTTPException(400, "Budget limit must be positive")
    try:
        datetime.strptime(f"{month}-01", "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(400, "Month must be YYYY-MM") from exc

    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO budgets (user_id, category, limit_amt, month) VALUES (?,?,?,?)
               ON CONFLICT(user_id, category, month) DO UPDATE SET limit_amt=excluded.limit_amt""",
            (user["sub"], category, limit_amt, month)
        )
    return RedirectResponse("/transactions/budgets", status_code=303)


# ── API endpoints (JSON) — for JS charts ─────────────────

@router.get("/api/summary")
async def api_summary(user=Depends(get_current_user)):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM transactions WHERE user_id=?", (user["sub"],))
        rows = [dict(r) for r in cur.fetchall()]

    income   = sum(r["amount"] for r in rows if r["type"] == "income")
    expenses = sum(r["amount"] for r in rows if r["type"] == "expense")

    # By category
    by_cat = {}
    for r in rows:
        if r["type"] == "expense":
            by_cat[r["category"]] = by_cat.get(r["category"], 0) + r["amount"]

    # By month
    by_month = {}
    for r in rows:
        m = str(r["date"])[:7]
        if m not in by_month:
            by_month[m] = {"income": 0, "expense": 0}
        by_month[m][r["type"]] += r["amount"]

    return JSONResponse({
        "total_income":   round(income, 2),
        "total_expenses": round(expenses, 2),
        "balance":        round(income - expenses, 2),
        "by_category":    {k: round(v, 2) for k, v in by_cat.items()},
        "by_month":       {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in sorted(by_month.items())},
        "transaction_count": len(rows),
    })
