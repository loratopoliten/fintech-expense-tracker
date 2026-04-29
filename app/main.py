"""
FinTrack v2 — Boosted Personal Finance Tracker
FastAPI + Jinja2 templates + Chart.js frontend
Deploy: Railway (app) + Supabase (PostgreSQL)
"""

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os

from app.database import init_db
from app.routes import auth, transactions, scoring, dashboard

app = FastAPI(title="FinTrack", version="2.0.0", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router,         prefix="/auth",         tags=["auth"])
app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
app.include_router(scoring.router,      prefix="/scoring",      tags=["scoring"])
app.include_router(dashboard.router,    prefix="",              tags=["dashboard"])


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "FinTrack running", "version": "2.0.0"}


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")
