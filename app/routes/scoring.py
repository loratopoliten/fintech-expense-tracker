from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import json
from app.database import db_cursor, USE_POSTGRES
from app.utils.auth import get_current_user
from app.utils.scoring import build_summary_from_db, compute_score

router = APIRouter()
templates = Jinja2Templates(directory="templates")
P = "%s" if USE_POSTGRES else "?"


@router.get("", response_class=HTMLResponse)
async def score_page(request: Request, user=Depends(get_current_user)):
    data = _compute_for_user(user["sub"])
    return templates.TemplateResponse("scoring/score.html",
        {"request": request, "user": user, **data})


@router.get("/api/compute")
async def api_compute(user=Depends(get_current_user)):
    return JSONResponse(_compute_for_user(user["sub"]))


def _compute_for_user(user_id: int) -> dict:
    with db_cursor() as cur:
        cur.execute(f"SELECT * FROM transactions WHERE user_id={P}", (user_id,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute(f"SELECT * FROM budgets WHERE user_id={P}", (user_id,))
        budgets = [dict(r) for r in cur.fetchall()]

    if not rows:
        return {
            "score": 0, "band": "needs_work", "has_data": False,
            "breakdown": {k: 0 for k in ["income_stability", "savings_health",
                          "budget_discipline", "emergency_fund", "spending_diversity"]},
            "tips": ["Add your first transaction to generate your Financial Health Score!"],
            "savings_rate": 0, "emergency_months": 0,
        }

    summary = build_summary_from_db(rows, budgets)
    result  = compute_score(summary)
    result.update({
        "has_data": True,
        "savings_rate": round(summary.savings_rate * 100, 1),
        "emergency_months": round(summary.emergency_fund_months, 1),
    })

    with db_cursor() as cur:
        cur.execute(
            f"INSERT INTO financial_scores (user_id,score,breakdown,band,tips) VALUES ({P},{P},{P},{P},{P})",
            (user_id, result["score"], json.dumps(result["breakdown"]),
             result["band"], json.dumps(result["tips"])))

    return result
