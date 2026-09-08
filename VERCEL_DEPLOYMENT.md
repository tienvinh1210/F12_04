# Vercel Deployment Guide

Deploy the Livestock Dashboard (frontend + FastAPI API) to [Vercel](https://vercel.com) with Supabase as the database.

---

## Architecture on Vercel

```
https://your-app.vercel.app
├── /login.html, /dashboard.html   → static files (frontend/)
├── /css, /js, /assets             → static files
└── /api/*                         → Python serverless (api/index.py → FastAPI)
                                          ↓
                                    Supabase PostgreSQL
```

| Component | Host |
|-----------|------|
| Frontend (HTML/CSS/JS) | Vercel static |
| API (FastAPI) | Vercel Python serverless (`api/index.py`) |
| Database | Supabase (external) |
| Email cron | Vercel Cron (daily on Hobby) or free external cron |

---

## Troubleshooting login on Vercel

1. Open `https://YOUR-APP.vercel.app/api/health` — must return `{"status":"ok"}`
2. Confirm Vercel env vars include `DATABASE_URL` (pooler **6543**, `@` → `%40`) and `JWT_SECRET`
3. Set `CORS_ORIGINS=https://YOUR-APP.vercel.app` and **redeploy**
4. Check **Deployments → Functions** logs for `/api/auth/login` errors
5. Hard-refresh login (`Cmd+Shift+R`) so the browser uses `/api` (same origin)

---

## Prerequisites

Complete these **before** deploying to Vercel:

1. **Supabase project** set up — see [SUPABASE_SETUP.md](SUPABASE_SETUP.md)
2. Schema applied (`database/001_schema.sql`)
3. Data seeded (`python scripts/seed.py --force` with `Data.csv`)
4. **GitHub account** (recommended for auto-deploy)
5. Code pushed to a GitHub repository

---

## Step 1 — Push code to GitHub

```bash
cd /path/to/COMP3888
git init
git add .
git commit -m "Livestock Dashboard initial deploy"
git branch -M main
git remote add origin https://github.com/tienvinh1210/F12_04.git
# or if origin exists:
# git remote set-url origin https://github.com/tienvinh1210/F12_04.git
git push -u origin main
```

Ensure `.env` and `backend/.env` are **not** committed (they are in `.gitignore`).

---

## Step 2 — Create a Vercel project

### Option A: Vercel Dashboard (recommended)

1. Go to [vercel.com/new](https://vercel.com/new)
2. **Import** your GitHub repository
3. Configure the project:

| Setting | Value |
|---------|--------|
| **Framework Preset** | Other |
| **Root Directory** | `.` (project root — **not** `frontend/`) |
| **Build Command** | leave empty |
| **Output Directory** | leave empty |

4. Do **not** deploy yet — add environment variables first (Step 3)

### Option B: Vercel CLI

```bash
npm i -g vercel
cd /path/to/COMP3888
vercel login
vercel          # preview deploy
vercel --prod   # production deploy
```

---

## Step 3 — Environment variables

In Vercel: **Project → Settings → Environment Variables**

Add all of these for **Production** and **Preview**:

| Variable | Example / notes |
|----------|-----------------|
| `DATABASE_URL` | `postgresql://postgres.[ref]:[PASSWORD]@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres` |
| `SUPABASE_URL` | `https://[ref].supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | From Supabase → Settings → API |
| `SUPABASE_ANON_KEY` | From Supabase → Settings → API |
| `JWT_SECRET` | Random 64-char hex (`openssl rand -hex 32`) |
| `JWT_EXPIRY_HOURS` | `24` |
| `CRON_SECRET` | Random secret (`openssl rand -hex 24`) |
| `CORS_ORIGINS` | `https://your-app.vercel.app` (update after first deploy) |
| `DEFAULT_TIMEZONE` | `Australia/Sydney` |
| `DEFAULT_FARM_ID` | `KF` |
| `EMAIL_PROVIDER` | `smtp` or `resend` |
| `EMAIL_FROM` | Your sender email |
| `EMAIL_DRY_RUN` | `false` (production) |
| `SMTP_HOST` | `smtp.gmail.com` (if using SMTP) |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | Your Gmail address |
| `SMTP_PASSWORD` | Gmail app password |
| `SMTP_USE_TLS` | `true` |

### Important: `DATABASE_URL` password encoding

If your Supabase password contains `@`, `#`, or `%`, URL-encode them:

| Character | Encoded |
|-----------|---------|
| `@` | `%40` |
| `#` | `%23` |
| `%` | `%25` |

Example: password `pass@word` → `pass%40word` in the connection string.

### Important: use the connection pooler

For serverless, use Supabase **Session pooler** on port **6543**:

```
postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres
```

---

## Step 4 — Email cron (Hobby-friendly)

Vercel **Hobby** only allows **once-per-day** cron jobs. This project uses:

```json
"crons": [{ "path": "/api/email/process-due", "schedule": "0 23 * * *" }]
```

That runs **once daily at 23:00 UTC** (~9–10am Australia/Sydney depending on DST).

No Pro plan required. Vercel Cron uses **HTTP GET** (not POST). When `CRON_SECRET` is set in the project env, Vercel sends `Authorization: Bearer <CRON_SECRET>`; the API also accepts `x-vercel-cron: 1` and `?cron_secret=`.

### Optional: run more often for free (external cron)

If you need checks every 15 minutes without upgrading Vercel:

1. Sign up at [cron-job.org](https://cron-job.org) (free)
2. Create a job:
   - URL: `https://YOUR-APP.vercel.app/api/email/process-due?cron_secret=YOUR_CRON_SECRET`
   - Method: `POST`
   - Schedule: every 15 minutes
3. Keep `CRON_SECRET` in Vercel env vars (and in the URL above)

You can then remove the `crons` block from `vercel.json` entirely if you only use the external service.

---

## Step 4b — Cold starts: slim light API + keep-warm + Fluid

Login and filter choices go through a **slim** function (`api/light/`) without pandas/matplotlib/reportlab. Charts/data/reports stay on `api/index.py`.

| Path | Function |
|------|----------|
| `/api/health`, `/api/auth/*`, `/api/filters/*`, `/api/summary/*`, `/api/charts/timeseries*`, `/api/charts/distribution` | `api/light/` (slim) |
| `/api/charts/custom`, `/api/data/*`, cohorts/reports/email/admin | `api/index.py` (full) |

### Enable Fluid Compute (Vercel dashboard)

1. Open the project → **Settings** → **Functions**
2. Turn **Fluid Compute** **on** (available on Hobby; older projects may need a manual toggle)
3. Redeploy if the UI asks you to

Fluid improves instance reuse; it does not replace keep-warm for a low-traffic demo app.

### Function region (critical for Supabase Sydney)

`vercel.json` sets `"regions": ["syd1"]` so Python functions run in **Sydney**, next to the Supabase `ap-southeast-2` pooler. The Vercel default (`iad1` US East) adds multi-second latency on every DB query (choices, grain, login).

Confirm under **Settings → Functions → Region** (or after deploy, check that `vercel.json` regions applied). Hobby allows one region.

### External keep-warm (Hobby — every 4–5 minutes)

Vercel Hobby cron is once/day, so use a free external ping to keep the **light** function warm:

1. Sign up at [cron-job.org](https://cron-job.org) (or equivalent)
2. Create a job:
   - **URL:** `https://f12-04.vercel.app/api/health` (or your production URL)
   - **Method:** `GET`
   - **Schedule:** every **5 minutes**
3. Optional second job (warms the heavy charts function before demos):
   - **URL:** `https://f12-04.vercel.app/api/health` is light-only — for grain, hit a cheap authenticated path during manual demo warm-up, or accept first chart load after idle may be slower

After keep-warm is active, typical login should stay well under the old ~5s cold path.

---

## Step 5 — Deploy

### Via GitHub (auto-deploy)

Push to `main` — Vercel deploys automatically.

### Via CLI

```bash
vercel --prod
```

First deploy URL will look like: `https://livestock-dashboard-abc123.vercel.app`

---

## Step 6 — Post-deploy configuration

### Update CORS

After you know your production URL, update in Vercel env vars:

```
CORS_ORIGINS=https://your-app.vercel.app
```

If you add a custom domain later, include both:

```
CORS_ORIGINS=https://your-app.vercel.app,https://dashboard.yourfarm.com
```

Redeploy after changing env vars.

### Verify the deployment

```bash
# Health check
curl https://your-app.vercel.app/api/health

# Login
curl -X POST https://your-app.vercel.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

Open in browser:

```
https://your-app.vercel.app/login.html
```

### Change default passwords

Before sharing with clients, change passwords via the API or re-run seed with new credentials.

---

## Step 7 — Custom domain (optional)

1. Vercel → **Project → Settings → Domains**
2. Add your domain (e.g. `dashboard.yourfarm.com`)
3. Add the DNS records Vercel provides (CNAME or A record)
4. Update `CORS_ORIGINS` to include the new domain
5. Redeploy

---

## Project files reference

| File | Purpose |
|------|---------|
| `vercel.json` | Routes, static files, cron, security headers |
| `api/index.py` | Vercel serverless entry (Mangum + FastAPI) |
| `api/requirements.txt` | Python dependencies for serverless |
| `backend/app/` | FastAPI application code |
| `frontend/` | Static HTML/CSS/JS |

### How routing works

```
/api/health          → api/index.py (FastAPI)
/api/auth/login      → api/index.py
/login.html          → frontend/login.html
/dashboard.html      → frontend/dashboard.html
/                    → frontend/index.html
```

The frontend uses same-origin `/api` in production (no separate API URL needed).

---

## Vercel plan limits

| Feature | Hobby (free) | Pro |
|---------|--------------|-----|
| Serverless timeout | 10s default (30s max with config) | Up to 300s |
| Cron jobs | 2 per account | More |
| Bandwidth | 100 GB/month | Higher |
| Cold starts | Yes (Python) | Yes, faster |

Heavy operations (PDF reports, large exports) may hit the timeout on Hobby. If reports fail in production, upgrade to Pro or move the API to Render/Railway (see [DEPLOYMENT.md](DEPLOYMENT.md) Option A).

Hobby tier uses the default serverless timeout. Heavy PDF/report jobs may need Pro or an external API host (see [DEPLOYMENT.md](DEPLOYMENT.md) Option A).

Note: do not add a `functions` block alongside `builds` in `vercel.json` — Vercel rejects that combination.

---

## Troubleshooting

### `Failed to fetch` on login

- Check `https://your-app.vercel.app/api/health` returns `{"status":"ok"}`
- Verify all env vars are set in Vercel (especially `DATABASE_URL`, `JWT_SECRET`)
- Check Vercel → **Deployments → Functions** logs for errors

### `500` on API routes

- Open Vercel function logs
- Common causes: wrong `DATABASE_URL`, password not URL-encoded, pooler port wrong
- Test connection locally with the same `DATABASE_URL`

### CORS errors

- Set `CORS_ORIGINS` to your exact Vercel URL (no trailing slash)
- Include custom domain if used
- Redeploy after env var changes

### Cron emails not sending

- Cron only runs on **production** deploys
- Hobby plan: once daily at 23:00 UTC (see `vercel.json`)
- For more frequent runs, use a free external cron (cron-job.org) with `?cron_secret=`
- Set `EMAIL_DRY_RUN=false`
- Check function logs for `/api/email/process-due`

### Build fails — Python dependencies

- Ensure `api/requirements.txt` lists packages directly (Vercel cannot parse `-r ../backend/...`)
- Matplotlib/reportlab can make builds slow — this is normal

### Static files 404

- Confirm **Root Directory** is project root (`.`), not `frontend/`
- Check `vercel.json` routes match your file structure

---

## Production checklist

- [ ] Supabase schema applied and `Data.csv` seeded (12,117 rows)
- [ ] All Vercel env vars set
- [ ] `CORS_ORIGINS` matches production URL
- [ ] `JWT_SECRET` and `CRON_SECRET` are strong random values
- [ ] Default passwords changed (`admin123`, etc.)
- [ ] `EMAIL_DRY_RUN=false` and email tested (Send Now on Reports page)
- [ ] Cron secret updated in `vercel.json`
- [ ] `GET /api/health` returns 200
- [ ] Login and dashboard load correctly
- [ ] `backend/.env` and secrets not committed to git

---

## Related docs

- [SUPABASE_SETUP.md](SUPABASE_SETUP.md) — database setup
- [DEPLOYMENT.md](DEPLOYMENT.md) — alternative split deploy (API on Render)
- [README.md](README.md) — local development
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) — folder layout
