# Supabase Setup Guide — Livestock Dashboard

Complete step-by-step instructions for connecting the Livestock Dashboard to Supabase PostgreSQL and Storage. This project uses **custom JWT auth** (not Supabase Auth) and connects from the **Python FastAPI backend only** via the service role / direct Postgres connection.

---

## Table of contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Create a Supabase project](#3-create-a-supabase-project)
4. [Collect credentials](#4-collect-credentials)
5. [Run the database schema](#5-run-the-database-schema)
6. [Verify tables and seed rows](#6-verify-tables-and-seed-rows)
7. [Configure environment variables](#7-configure-environment-variables)
8. [Seed users and KF sample data](#8-seed-users-and-kf-sample-data)
9. [Create storage buckets](#9-create-storage-buckets)
10. [Storage policies](#10-storage-policies)
11. [Row Level Security (RLS)](#11-row-level-security-rls)
12. [Upload farm logos (optional)](#12-upload-farm-logos-optional)
13. [Connect from Vercel](#13-connect-from-vercel)
14. [Local development with Supabase](#14-local-development-with-supabase)
15. [Troubleshooting](#15-troubleshooting)
16. [Production security checklist](#16-production-security-checklist)

---

## 1. Overview

| Component | Where it lives | How the app uses it |
|-----------|----------------|---------------------|
| PostgreSQL | Supabase | All animal data, users, email schedules |
| Storage | Supabase | Farm logos, CSV archives, generated reports |
| Supabase Auth | **Not used** | App uses custom `users` table + JWT |
| Connection | Backend only | `DATABASE_URL` with pooler (port 6543) |

**What you will end up with:**

- 8 database tables (`farms`, `users`, `user_farm_access`, `animal_data`, etc.)
- Farm **KF** (Killara Feedlot) pre-inserted by schema
- 3 default users after running the seed script
- ~12,000 sample animal records for KF
- 3 storage buckets for logos, uploads, and reports

---

## 2. Prerequisites

- A [Supabase account](https://supabase.com) (free tier is sufficient for development)
- This repository cloned locally
- Python 3.11+ installed
- Terminal access

Optional but recommended:

- [Supabase CLI](https://supabase.com/docs/guides/cli) for advanced workflows
- [Vercel account](https://vercel.com) if deploying the full stack

---

## 3. Create a Supabase project

### Step 3.1 — Sign in and create project

1. Go to [https://supabase.com/dashboard](https://supabase.com/dashboard)
2. Click **New project**
3. Fill in:
   - **Name:** `livestock-dashboard` (or any name)
   - **Database password:** Generate a strong password and **save it** — you cannot recover it later without a reset
   - **Region:** Choose the closest region to your users
     - **Recommended for Australia:** `Oceania (Sydney)` if available, otherwise `Southeast Asia (Singapore)`
4. Click **Create new project**
5. Wait 1–2 minutes for provisioning to complete

### Step 3.2 — Note your project reference

Your project URL looks like:

```
https://abcdefghijklmnop.supabase.co
```

The part before `.supabase.co` is your **Project Reference** (e.g. `abcdefghijklmnop`). You will need this for connection strings and environment variables.

---

## 4. Collect credentials

Open your project in the Supabase Dashboard, then go to **Project Settings** (gear icon) → **API**.

### 4.1 — API keys

| Key | Location | Used by |
|-----|----------|---------|
| **Project URL** | Settings → API → Project URL | `SUPABASE_URL` |
| **anon public** | Settings → API → Project API keys | `SUPABASE_ANON_KEY` (optional) |
| **service_role** | Settings → API → Project API keys | `SUPABASE_SERVICE_ROLE_KEY` |

> **Warning:** Never put `service_role` in frontend code or commit it to git. It bypasses Row Level Security.

### 4.2 — Database connection string

Go to **Project Settings** → **Database** → **Connection string**.

Select **URI** and **Session pooler** (recommended for Vercel serverless):

```
postgresql://postgres.[PROJECT_REF]:[YOUR-PASSWORD]@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres
```

| Setting | Value | Notes |
|---------|-------|-------|
| Host | `aws-0-[region].pooler.supabase.com` | Region varies by project |
| Port | `6543` | **Transaction pooler** — use for serverless |
| Port | `5432` | **Direct connection** — use for long-running servers or `seed.py` if pooler fails |
| User | `postgres.[PROJECT_REF]` | Pooler format |
| Password | Your database password from Step 3.1 |
| Database | `postgres` | Default database name |

Copy this string — it becomes your `DATABASE_URL`.

### 4.3 — Generate app secrets

Run these locally to create secure secrets:

```bash
# JWT secret (min 32 characters)
openssl rand -hex 32

# Cron secret (for email scheduler endpoint)
openssl rand -hex 24
```

Save both values for your `.env` file.

---

## 5. Run the database schema

The schema file is at `database/001_schema.sql` in this repository.

### Step 5.1 — Open the SQL Editor

1. In Supabase Dashboard, click **SQL Editor** in the left sidebar
2. Click **New query**

### Step 5.2 — Paste and run the schema

1. Open `database/001_schema.sql` in your code editor
2. Copy the **entire file**
3. Paste into the Supabase SQL Editor
4. Click **Run** (or press `Cmd+Enter` / `Ctrl+Enter`)

You should see **Success. No rows returned** (or similar). Some `INSERT` statements may show row counts.

### Step 5.3 — What the schema creates

**Tables:**

| Table | Purpose |
|-------|---------|
| `farms` | Multi-tenant farm registry |
| `users` | Custom auth (username + scrypt password hash) |
| `user_farm_access` | Which users can access which farms |
| `animal_data` | Main livestock measurement records |
| `animal_data_snapshots` | Pre-upload backups |
| `email_schedules` | Scheduled report emails |
| `data_uploads` | CSV upload audit log |

**Indexes** on `animal_data` for fast filtering by date, breed, treatment, mob, sex, and year.

**Seed data included in schema:**

- Farm `KF` — Killara Feedlot
- Placeholder users: `admin`, `owner`, `user` (passwords fixed by seed script)

> If you re-run the full schema on an existing project, `CREATE TABLE` will fail. For fresh installs only run it once. For updates, run individual migration statements.

---

## 6. Verify tables and seed rows

### Option A — Table Editor (GUI)

1. Go to **Table Editor** in the left sidebar
2. Confirm these tables exist: `farms`, `users`, `animal_data`, `email_schedules`
3. Click `farms` — you should see one row:
   - `farm_id`: `KF`
   - `farm_name`: `Killara Feedlot`

### Option B — SQL verification query

In **SQL Editor**, run:

```sql
-- Tables exist
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- Farm KF exists
SELECT * FROM farms WHERE farm_id = 'KF';

-- Placeholder users exist (3 rows)
SELECT id, username, is_admin FROM users ORDER BY id;

-- Animal data count (0 until seed script runs)
SELECT COUNT(*) AS animal_count FROM animal_data WHERE farm_id = 'KF';
```

Expected before seeding:

| Check | Expected |
|-------|----------|
| Tables | 7+ public tables |
| `farms` | 1 row (`KF`) |
| `users` | 3 rows |
| `animal_data` | 0 rows |

---

## 7. Configure environment variables

### Step 7.1 — Create backend `.env`

```bash
cp backend/.env.example backend/.env
```

### Step 7.2 — Fill in values

Edit `backend/.env`:

```bash
# Required — Session pooler connection string from Supabase Dashboard
DATABASE_URL=postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres

# Required — from Settings → API
SUPABASE_URL=https://[PROJECT_REF].supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Required — generate with openssl rand -hex 32
JWT_SECRET=your-64-char-hex-string-here
JWT_EXPIRY_HOURS=24

# Email (optional for dev — set EMAIL_DRY_RUN=true to skip sending)
RESEND_API_KEY=re_...
EMAIL_FROM=reports@yourdomain.com
EMAIL_DRY_RUN=true

# CORS — add your Vercel URL when deploying
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Cron — generate with openssl rand -hex 24
CRON_SECRET=your-cron-secret-here

DEFAULT_TIMEZONE=Australia/Sydney
DEFAULT_FARM_ID=KF

# Logos — local path until Storage is configured
LOGOS_LOCAL_PATH=./frontend/assets/logos
```

### Variable reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Postgres connection string (pooler port 6543) |
| `SUPABASE_URL` | Yes | Project URL for Storage API (future use) |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Backend Storage uploads (admin logos, CSV archive) |
| `SUPABASE_ANON_KEY` | No | Not needed unless frontend calls Supabase directly |
| `JWT_SECRET` | Yes | Signs login tokens |
| `JWT_EXPIRY_HOURS` | No | Default `24` |
| `EMAIL_DRY_RUN` | No | `true` = log emails without sending |
| `CRON_SECRET` | Yes (prod) | Protects `/api/email/process-due` |
| `CORS_ORIGINS` | Yes | Comma-separated allowed frontend origins |

---

## 8. Seed users and KF sample data

The schema inserts placeholder password hashes. The seed script replaces them with real scrypt hashes and loads ~12,000 animal records.

### Step 8.1 — Install Python dependencies

```bash
cd /path/to/COMP3888
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

### Step 8.2 — Run the seed script

```bash
# Ensure backend/.env has a valid DATABASE_URL
python scripts/seed.py
```

Expected output:

```
Seeded users: admin, owner, user
Seeded farm KF (Killara Feedlot)
Seeded 12000 animal records for KF
Seed complete.
```

### Step 8.3 — Verify seed in Supabase

Run in SQL Editor:

```sql
SELECT COUNT(*) FROM animal_data WHERE farm_id = 'KF';
-- Expected: ~12000

SELECT MIN(date), MAX(date) FROM animal_data WHERE farm_id = 'KF';
-- Expected: dates in 2023–2024 range

SELECT username, is_admin FROM users;
-- admin=true, owner=true, user=false
```

### Default login credentials (change before production)

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | Admin — full access, real EIDs |
| `owner` | `owner123` | Admin — full access, real EIDs |
| `user` | `user123` | Viewer — EIDs shown as `*****` |

### Re-running the seed

- **Users:** Upserted safely (`ON CONFLICT` updates passwords)
- **Animal data:** Skipped if KF already has ≥1,000 rows; otherwise deleted and re-inserted

To force a full re-seed:

```sql
DELETE FROM animal_data WHERE farm_id = 'KF';
```

Then run `python scripts/seed.py` again.

### Seed fails with connection error?

Try the **direct connection** string (port `5432`) instead of the pooler:

```
postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
```

Note: direct connection uses `postgres` as the username (no `.[PROJECT_REF]` suffix).

---

## 9. Create storage buckets

Storage is used for farm header logos, CSV upload archives, and generated report PDFs.

### Step 9.1 — Open Storage

1. In Supabase Dashboard, click **Storage** in the left sidebar
2. Click **New bucket**

### Step 9.2 — Create three buckets

| Bucket name | Public | File size limit | Purpose |
|-------------|--------|-----------------|---------|
| `logos` | **Yes** | 1 MB | Farm header logos (`KF/01_killara.png`) |
| `uploads` | No | 50 MB | Archived CSV files after admin upload |
| `reports` | No | 20 MB | Generated PDF/HTML reports |

For each bucket:

1. Click **New bucket**
2. Enter the **Name** exactly as shown above
3. Toggle **Public bucket** on only for `logos`
4. Click **Create bucket**

### Step 9.3 — Folder structure (convention)

```
logos/
  KF/
    01_killara.png
    02_partner.png

uploads/
  KF/
    archive/
      KF_2025-01-22.csv

reports/
  KF/
    generated/
      abc123-report.pdf
```

The app currently serves logos from `LOGOS_LOCAL_PATH` by default. Storage integration for logos is available when `SUPABASE_SERVICE_ROLE_KEY` is set and files are uploaded via the admin API.

---

## 10. Storage policies

Private buckets (`uploads`, `reports`) deny public access by default — only the backend with `service_role` can read/write.

For the public `logos` bucket, add a read policy so the dashboard can display images via public URLs.

### Step 10.1 — Open Storage policies

1. Go to **Storage** → click the `logos` bucket
2. Click **Policies** tab
3. Click **New policy**

### Step 10.2 — Public read policy for logos

Choose **For full customization**, then run in **SQL Editor**:

```sql
-- Allow anyone to read files in the logos bucket
CREATE POLICY "Public logo read"
ON storage.objects
FOR SELECT
USING (bucket_id = 'logos');
```

### Step 10.3 — Service role write (backend uploads)

The `service_role` key bypasses RLS, so the backend can upload logos without extra policies. If you later use the `anon` key from the browser, add authenticated upload policies per farm.

### Step 10.4 — Optional: restrict uploads bucket to service role only

No extra policy needed — private buckets are inaccessible to anonymous users by default.

---

## 11. Row Level Security (RLS)

The schema enables RLS on `animal_data` and `farms`:

```sql
ALTER TABLE animal_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE farms ENABLE ROW LEVEL SECURITY;
```

### How this project handles RLS

The FastAPI backend connects with `DATABASE_URL` using the **postgres** database user (via pooler). This connection **bypasses RLS** — which is intentional because:

1. Auth is custom JWT, not Supabase Auth
2. Farm access is enforced in Python (`assert_farm_access`)
3. EID anonymization is enforced in the API response layer

**Do not expose `DATABASE_URL` or `service_role` to the browser.**

### If you later add Supabase client in the frontend

You would need policies like:

```sql
-- Example only — requires Supabase Auth integration
CREATE POLICY "Users see own farms"
ON animal_data
FOR SELECT
USING (
  farm_id IN (
    SELECT farm_id FROM user_farm_access
    WHERE user_id = auth.uid()::int
  )
);
```

This is **out of scope** for the current build.

---

## 12. Upload farm logos (optional)

### Option A — Local logos (default, no Storage needed)

Place PNG/JPG files in:

```
frontend/assets/logos/KF/01_killara.png
frontend/assets/logos/KF/02_partner.png
```

Filenames are sorted alphabetically in the dashboard header.

### Option B — Supabase Storage

1. Go to **Storage** → `logos` bucket
2. Create folder `KF`
3. Upload images (PNG/JPG/SVG, recommended &lt; 100 KB each)
4. Public URL format:
   ```
   https://[PROJECT_REF].supabase.co/storage/v1/object/public/logos/KF/01_killara.png
   ```

Update the backend `LOGOS_LOCAL_PATH` or extend `farms.py` to read from Storage when configured.

---

## 13. Connect from Vercel

When deploying to Vercel, add the same environment variables in the Vercel project settings.

### Step 13.1 — Vercel environment variables

Go to your Vercel project → **Settings** → **Environment Variables**:

| Name | Environments | Value |
|------|--------------|-------|
| `DATABASE_URL` | Production, Preview | Pooler URI (port 6543) |
| `SUPABASE_URL` | Production, Preview | `https://[PROJECT_REF].supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Production, Preview | From Supabase API settings |
| `JWT_SECRET` | Production, Preview | Random 32+ byte hex |
| `CRON_SECRET` | Production | Random secret |
| `CORS_ORIGINS` | Production | `https://your-app.vercel.app` |
| `EMAIL_DRY_RUN` | Preview | `true` |
| `EMAIL_DRY_RUN` | Production | `false` |
| `DEFAULT_TIMEZONE` | All | `Australia/Sydney` |

### Step 13.2 — Email cron job

`vercel.json` schedules `/api/email/process-due` every 15 minutes. Vercel cron cannot set custom headers, so pass the secret as a query parameter in the Vercel cron config:

```
/api/email/process-due?cron_secret=YOUR_CRON_SECRET
```

Or set `CRON_SECRET` in Vercel and configure the cron path in the Vercel dashboard to include the query string.

### Step 13.3 — Connection pooler and serverless

Always use the **Session pooler** (`port 6543`) on Vercel. Direct connections (`port 5432`) exhaust connection limits under serverless concurrency.

---

## 14. Local development with Supabase

### Recommended workflow

```bash
# Terminal 1 — API (reads backend/.env)
cd backend
source ../.venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
python -m http.server 3000
```

Open [http://localhost:3000/login.html](http://localhost:3000/login.html)

### Test API connection

```bash
curl http://localhost:8000/api/health
# {"status":"ok","version":"1.0.0"}

curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### Alternative: local Postgres (no Supabase)

For offline development, use Docker instead:

```bash
docker compose up -d
# Uses local postgres://postgres:postgres@localhost:5432/livestock
```

Update `backend/.env` with the local `DATABASE_URL`, then run `python scripts/seed.py`.

---

## 15. Troubleshooting

### `connection refused` or `timeout`

| Cause | Fix |
|-------|-----|
| Wrong password | Reset in Supabase → Settings → Database → Reset password |
| Wrong port | Use `6543` for pooler, `5432` for direct |
| IP blocked | Supabase free tier allows all IPs by default; check **Database → Network restrictions** |
| Pooler user format | Pooler user must be `postgres.[PROJECT_REF]`, not just `postgres` |

### `SSL connection required`

Add `?sslmode=require` to the end of `DATABASE_URL`:

```
postgresql://...postgres?sslmode=require
```

### `relation "farms" does not exist`

Schema was not applied. Re-run `database/001_schema.sql` in SQL Editor.

### `duplicate key value violates unique constraint`

Schema was partially applied. Either:
- Drop tables and re-run schema (destructive), or
- Skip the failing `INSERT` statements and run `python scripts/seed.py`

### Login returns 401 after seed

1. Confirm seed ran: `SELECT password_hash FROM users WHERE username='admin'` — should not start with `$scrypt$placeholder_`
2. Re-run: `python scripts/seed.py`

### Seed is slow or times out

- Normal for ~12,000 rows (1–3 minutes)
- Use direct connection (port 5432) for bulk inserts
- Reduce rows in `scripts/seed.py` (`target_rows=1000`) for dev

### `too many connections` on Vercel

- Switch from direct (`5432`) to pooler (`6543`)
- Ensure you are not opening a new pool per request (the app uses `SimpleConnectionPool`)

### Storage upload fails

- Confirm bucket exists and name matches exactly (`logos`, `uploads`, `reports`)
- Confirm `SUPABASE_SERVICE_ROLE_KEY` is set in backend env
- Check file size limits on the bucket

### RLS blocks queries

If you connect with a non-superuser role, RLS may block reads. This app expects the postgres/pooler connection which bypasses RLS. Do not use the `anon` key for database queries.

---

## 16. Production security checklist

Before going live:

- [ ] Changed default passwords (`admin123`, `owner123`, `user123`)
- [ ] `JWT_SECRET` is a unique random value (not the dev default)
- [ ] `CRON_SECRET` is set and not committed to git
- [ ] `SUPABASE_SERVICE_ROLE_KEY` is only in Vercel/backend env (never in frontend)
- [ ] `DATABASE_URL` is only in backend env
- [ ] `CORS_ORIGINS` lists only your production domain
- [ ] `EMAIL_DRY_RUN=false` in production (after Resend is configured)
- [ ] Supabase **daily backups** enabled (Settings → Database → Backups)
- [ ] Review **Database → Network restrictions** if you need IP allowlisting
- [ ] `uploads` and `reports` buckets remain **private**
- [ ] Verified login and farm data access for all three roles

---

## Quick reference

| Task | Command / Location |
|------|-------------------|
| Apply schema | Supabase SQL Editor → paste `database/001_schema.sql` |
| Seed data | `python scripts/seed.py` |
| Backend env | `backend/.env` |
| Health check | `GET /api/health` |
| Supabase Dashboard | [supabase.com/dashboard](https://supabase.com/dashboard) |
| Connection strings | Settings → Database → Connection string |
| API keys | Settings → API |

---

## Related docs

- [README.md](README.md) — project overview and quick start
- [DEPLOYMENT.md](DEPLOYMENT.md) — Vercel + Render deployment options
- [AUTH_AND_ROLES.md](AUTH_AND_ROLES.md) — user roles and EID privacy
- [DATA_MODEL.md](DATA_MODEL.md) — CSV format and table columns
- [database/001_schema.sql](database/001_schema.sql) — full SQL schema
