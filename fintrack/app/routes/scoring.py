"""Financial Health Score routes — powered by CapitalPyre-style scoring engine."""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import json
from app.database import db_cursor
from app.utils.auth import get_current_user
from app.utils.scoring import build_summary_from_db, compute_score

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def score_page(request: Request, user=Depends(get_current_user)):
    score_data = _compute_for_user(user["sub"])
    return templates.TemplateResponse("scoring/score.html", {
        "request": request,
        "user": user,
        **score_data,
    })


@router.get("/api/compute")
async def api_compute_score(user=Depends(get_current_user)):
    return JSONResponse(_compute_for_user(user["sub"]))


def _compute_for_user(user_id: int) -> dict:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM transactions WHERE user_id=?", (user_id,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM budgets WHERE user_id=?", (user_id,))
        budgets = [dict(r) for r in cur.fetchall()]

    if not rows:
        return {
            "score": 0, "band": "needs_work",
            "breakdown": {k: 0 for k in ["income_stability","savings_health","budget_discipline","emergency_fund","spending_diversity"]},
            "tips": ["Add your first transaction to generate your Financial Health Score!"],
            "has_data": False,
        }

    summary    = build_summary_from_db(rows, budgets)
    result     = compute_score(summary)
    result["has_data"]     = True
    result["savings_rate"] = round(summary.savings_rate * 100, 1)
    result["emergency_months"] = round(summary.emergency_fund_months, 1)

    # Persist latest score
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO financial_scores (user_id, score, breakdown, band, tips) VALUES (?,?,?,?,?)",
            (user_id, result["score"], json.dumps(result["breakdown"]),
             result["band"], json.dumps(result["tips"]))
        )

    return result
