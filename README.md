# FinTrack v2 — Boosted Personal Finance Tracker

Upgraded from a basic CLI script into a full-stack Python web app with interactive charts, auth, budgets, and a Financial Health Score engine.

## Features

- **Auth** — register/login/logout, bcrypt + JWT cookies
- **Transactions** — income & expense tracking with categories, search, filter
- **Budgets** — monthly limits per category with animated progress bars
- **Dashboard** — monthly trend line chart, spending donut chart, score gauge
- **Financial Health Score** — 0–100 across 5 dimensions (CapitalPyre CRS pattern)
- **Deploy-ready** — Railway + Supabase, `railway.json` included

## Quick start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000 → register → start tracking.

## Deploy

See [DEPLOY.md](DEPLOY.md) — Railway + Supabase, free tier.

## Stack

| Layer | Tech |
|-------|------|
| Framework | FastAPI (Python 3.12) |
| Database | SQLite (local) → PostgreSQL/Supabase (prod) |
| Auth | bcrypt + JWT |
| Charts | Chart.js (CDN, no build step) |
| Deploy | Railway (app) + Supabase (DB) |
