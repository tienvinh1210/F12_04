# Livestock Dashboard

Python FastAPI backend + HTML/CSS/JS frontend for livestock feedlot performance analytics. Multi-tenant on Supabase PostgreSQL, deployable to **Vercel**.

## Features

- **7 dashboard pages**: Summary Stats, Time Series, Distributions, Cohorts, Data Management, Customise, Reports
- **Shared filter sidebar** with debounced queries, saved views (localStorage), EID privacy for non-admin users
- **JWT auth** with scrypt passwords (admin / owner / user roles)
- **Email scheduling** (daily/weekly/monthly/once) with cron worker
- **Admin CSV upload** with snapshot backup and skip/overwrite duplicates
- **Farm KF (Killara Feedlot)** seeded with real `Data.csv` (~12,117 records)

## Quick Start (Local)

### 1. Configure environment

```bash
cp backend/.env.example backend/.env
# Set DATABASE_URL to your Supabase pooler URL (port 6543; encode @ in password as %40)
```

### 2. Install & seed

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python scripts/seed.py --force
```

### 3. Run (HTML frontend + API)

**One process (recommended):**

```bash
cd backend && uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/login.html

**Or two processes:**

```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend && python -m http.server 3000
```

Open http://localhost:3000/login.html

### Default credentials

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Admin |
| owner | owner123 | Admin |
| user | user123 | Viewer (EIDs anonymized) |

## Deploy to Vercel

Repo: https://github.com/tienvinh1210/F12_04  

Full guide: **[VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md)**

Quick summary:
1. Complete [Supabase setup](SUPABASE_SETUP.md) and seed data
2. Push this repo to GitHub
3. Import on [vercel.com](https://vercel.com) — **Root Directory = `.`**
4. Add env vars (`DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGINS`, etc.)
5. Deploy → open `https://your-app.vercel.app/login.html`

After first deploy, set:

```
CORS_ORIGINS=https://your-app.vercel.app
```

then redeploy.

## API Health Check

```bash
curl https://your-app.vercel.app/api/health
# {"status":"ok","version":"1.0.0"}
```

## Project Structure

```
backend/app/          FastAPI application
frontend/             HTML/CSS/JS dashboard (primary UI)
api/                  Vercel serverless entry (Mangum)
database/             PostgreSQL schema
scripts/seed.py       Seed users + KF data from Data.csv
```

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for layout details.

## Tests

```bash
pytest backend/tests/ -v
```

## Runbook

- **Change passwords**: `PUT /api/auth/password` or re-run seed
- **Upload CSV**: `POST /api/admin/farms/KF/upload`
- **Email dry run**: `EMAIL_DRY_RUN=true`
- See `TESTING.md`, `DEPLOYMENT.md`, `00_BLUEPRINT_MASTER.md`
