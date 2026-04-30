"""
FinTrack — Boosted Personal Finance Tracker
Built on Python + FastAPI. Inspired by CapitalPyre's architecture.
Deploy via: Railway (API) + Render (scoring) + Supabase (DB)
"""

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os

from app.database import init_db
from app.routes import auth, transactions, scoring, dashboard

app = FastAPI(title="FinTrack", version="2.0.0", docs_url="/api/docs")

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]
allow_credentials = "*" not in cors_origins

# ── CORS (for frontend/API split like CapitalPyre) ─────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files & templates ────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ── Routes ──────────────────────────────────────────────────
app.include_router(auth.router,         prefix="/auth",         tags=["auth"])
app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
app.include_router(scoring.router,      prefix="/scoring",      tags=["scoring"])
app.include_router(dashboard.router,    prefix="",              tags=["dashboard"])

# ── Startup ─────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "FinTrack API running", "version": "2.0.0"}

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return RedirectResponse(url="/dashboard")
