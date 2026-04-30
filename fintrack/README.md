# FinTrack — Boosted Personal Finance Tracker

A full-stack Python web app — upgraded from a basic CLI tracker into a
production-ready system with auth, budgets, analytics, and a Financial Health
Score engine inspired by CapitalPyre's CRS scoring architecture.

## What's inside

| Layer | Tech |
|-------|------|
| Framework | FastAPI (Python 3.12) |
| Database | SQLite locally → PostgreSQL (Supabase) in prod |
| Auth | bcrypt passwords + JWT cookies |
| Scoring | Custom 5-dimension FHS engine |
| Deploy | Railway + Supabase (CapitalPyre method) |

## Features

- **User auth** — register, login, logout (bcrypt + JWT, pattern from Lab8 + CapitalPyre)
- **Transactions** — add income/expense with category, description, date
- **Budgets** — set monthly spending limits per category with progress bars
- **Dashboard** — monthly vs all-time summary, recent transactions
- **Financial Health Score** — 0–100 score across 5 dimensions:
  - Income Stability (25 pts)
  - Savings Health (25 pts)
  - Budget Discipline (20 pts)
  - Emergency Fund Coverage (15 pts)
  - Spending Diversity (15 pts)
- **Deploy-ready** — `railway.json`, `Procfile`, `Dockerfile`, `render.yaml`

## Quick start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
# → http://localhost:8000
```

## Deploy

See [DEPLOY.md](DEPLOY.md) for Railway + Supabase setup.

## Resources used

- `fintech-expense-tracker-main` — original CLI tracker (base logic)
- `capitalpyre_v4` — architecture: FastAPI microservice, CRS scoring engine, Railway deploy pattern
- `CSI315_Lab8` — auth pattern: bcrypt hashing, prepared statements, session management
- `iams-backend` — backend structural reference
