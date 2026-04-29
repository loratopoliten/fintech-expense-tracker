# 🚀 FinTrack — Deploy Guide (CapitalPyre Method)
## Railway + Supabase — free tier

---

## Local development (SQLite, no setup)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
# → http://localhost:8000
```

---

## Production deployment

### Step 1 — Supabase (PostgreSQL database)

1. [supabase.com](https://supabase.com) → Sign up → New project
2. Region: **South Africa** (closest to Botswana)
3. **Settings → Database → Connection string (URI)** → copy it
   ```
   postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres
   ```

### Step 2 — Railway (app hosting)

1. [railway.app](https://railway.app) → Sign up with GitHub
2. **New Project → Deploy from GitHub repo** → pick `fintech-expense-tracker`
3. Railway reads `railway.json` automatically — uses `requirements-postgres.txt`
4. **Variables** tab → add:

   | Key | Value |
   |-----|-------|
   | `DATABASE_URL` | your Supabase URI from Step 1 |
   | `JWT_SECRET` | any long random string |
   | `PORT` | `8000` |

5. Deploy → **Settings → Domains → Generate Domain**

Tables are created automatically on first startup — no SQL migrations needed.

---

## After deployment

- Push to GitHub → Railway auto-redeploys
- Custom domain: Railway → Settings → Domains → add yours

---

## Environment variables reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Prod only | Supabase PostgreSQL URI (`postgresql://` or `postgres://`) |
| `JWT_SECRET` | Yes (prod) | Long random string for JWT signing |
| `PORT` | Yes (prod) | Set to `8000` |
