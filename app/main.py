"""
FinTrack v2 — Boosted Personal Finance Tracker
FastAPI + Jinja2 templates + Chart.js frontend
Deploy: Railway (app) + Supabase (PostgreSQL)
"""

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os

from app.database import init_db
from app.routes import auth, transactions, scoring, dashboard
from app.services.scheduler_service import start_scheduler
from app.utils.auth import optional_user

app = FastAPI(title="FinTrack", version="2.0.0", docs_url="/api/docs")

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]
allow_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(auth.router,         prefix="/auth",         tags=["auth"])
app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
app.include_router(scoring.router,      prefix="/scoring",      tags=["scoring"])
app.include_router(dashboard.router,    prefix="",              tags=["dashboard"])

_scheduler = None


@app.on_event("startup")
async def startup():
    global _scheduler
    init_db()
    _scheduler = start_scheduler()


@app.get("/health")
def health():
    return {"status": "FinTrack running", "version": "2.0.0"}


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = optional_user(request)
    if user:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("landing.html", {"request": request})
