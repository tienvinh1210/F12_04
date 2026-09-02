# Livestock Dashboard

Python FastAPI backend + HTML/CSS/JS frontend for livestock feedlot performance analytics. Multi-tenant on Supabase PostgreSQL, deployable to Vercel.

## Features

- **7 dashboard pages**: Summary Stats, Time Series, Distributions, Cohorts, Data Management, Customise, Reports
- **Shared filter sidebar** with debounced queries, saved views (localStorage), EID privacy for non-admin users
- **JWT auth** with scrypt passwords (admin / owner / user roles)
- **Email scheduling** (daily/weekly/monthly/once) with cron worker
- **Admin CSV upload** with snapshot backup and skip/overwrite duplicates
- **Farm KF (Killara Feedlot)** seeded with ~12,000 sample records

## Quick Start (Local)

### 1. Start PostgreSQL

```bash
docker compose up -d
```

### 2. Configure environment

```bash
cp .env.example backend/.env
# Edit DATABASE_URL if needed (default: postgresql://postgres:postgres@localhost:5432/livestock)
```

### 3. Install dependencies & seed

```bash
pip install -r backend/requirements.txt
python scripts/seed.py
```

### 4. Run API

```bash
cd backend && uvicorn app.main:app --reload --port 8000
```

### 5. Serve frontend

```bash
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

See **[VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md)** for full step-by-step hosting instructions.

Quick summary:
1. Complete [Supabase setup](SUPABASE_SETUP.md) and seed data
2. Push repo to GitHub
3. Import project on [vercel.com](https://vercel.com) (root directory = `.`)
4. Add environment variables from `backend/.env.example`
5. Update `CORS_ORIGINS` and cron secret in `vercel.json`
6. Deploy → open `https://your-app.vercel.app/login.html`

Vercel cron runs `/api/email/process-due` every 15 minutes. Set `CRON_SECRET` and configure the cron header in Vercel dashboard.

## API Health Check

```bash
curl http://localhost:8000/api/health
# {"status":"ok","version":"1.0.0"}
```

## Project Structure

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for the correct folder layout and common mistakes.

```
backend/app/          FastAPI application
frontend/             Static HTML/CSS/JS dashboard
api/                  Vercel serverless entry
database/             PostgreSQL schema
scripts/seed.py       Seed users + KF sample data
admin-cli/admin.py    CLI for CSV upload
```

## Tests

```bash
pytest backend/tests/ -v
```

## Runbook

- **Change passwords**: `PUT /api/auth/password` or re-run seed with updated hashes
- **Upload CSV**: `POST /api/admin/farms/KF/upload` (filename: `KF_YYYY-MM-DD.csv`)
- **Email dry run**: Set `EMAIL_DRY_RUN=true` to skip Resend API calls
- **Rollback data**: Use `animal_data_snapshots` via admin API

See `TESTING.md`, `DEPLOYMENT.md`, and `00_BLUEPRINT_MASTER.md` for full specifications.
