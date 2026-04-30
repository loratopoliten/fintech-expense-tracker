# 🚀 FinTrack — Deployment Guide
## Railway + Supabase (CapitalPyre method) — $0/month

---

## Step 1 — Supabase (Database)

1. Go to [supabase.com](https://supabase.com) → Sign up free
2. Create new project → choose **South Africa** or **Europe** region (closest to Botswana)
3. Wait ~2 minutes for provisioning
4. Go to **Settings → Database** → copy the **Connection string (URI)**
   - Looks like: `postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres`
5. Save this — you'll need it for Railway

---

## Step 2 — Railway (App + API)

1. Go to [railway.app](https://railway.app) → Sign up with GitHub
2. Push this project to a GitHub repo
3. Click **New Project → Deploy from GitHub repo** → select your repo
4. Railway auto-detects `railway.json` and uses NIXPACKS
5. Add these environment variables in Railway dashboard:
   ```
   DATABASE_URL=<your Supabase connection string>
   JWT_SECRET=<generate a long random string — e.g. openssl rand -hex 32>
   PORT=8000
   ```
   > The app supports both `postgresql://...` and `postgres://...` connection strings.
6. Deploy → Railway gives you a URL like `https://fintrack.railway.app`

> **Note:** The app auto-creates all tables on first startup via `init_db()`.
> No SQL migrations needed — just deploy and go.

---

## Step 3 — Done ✅

Your app is live! Visit your Railway URL and register your first account.

- Database: Supabase (free, forever)
- App: Railway (~$1-2/month within $5 free credit)

---

## Local Development

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Copy env
cp .env.example .env
# (no edits needed for local SQLite)

# 3. Run
uvicorn app.main:app --reload

# 4. Open http://localhost:8000
```

---

## Switching to PostgreSQL locally

Edit `.env`:
```
DATABASE_URL=postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres
```

---

## Custom domain (optional)

In Railway → Project Settings → Domains → add your domain.
