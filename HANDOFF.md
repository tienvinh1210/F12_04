# HANDOFF.md — AI session context (COMP3888 Livestock Dashboard)

Read this before changing code. Prefer this file + source over older specs (`API_SPEC.md`, `UI_SPEC.md`, Streamlit docs) when they conflict.

```
repo: https://github.com/tienvinh1210/F12_04.git
branch: main
local: /Users/dang_tienthanh/Downloads/COMP3888
product: multi-tenant livestock feedlot analytics (farm KF = Killara Feedlot)
origin: rebuild of R/Shiny app → FastAPI + static HTML/JS + Supabase + Vercel
NOT: React, Next, Supabase Auth, Streamlit (Streamlit attempt reverted)
```

---

## Agent constraints (MUST / NEVER)

MUST:
- Match existing FastAPI + vanilla JS + Plotly patterns.
- Keep chart/summary hot paths on SQL (`backend/app/services/sql_agg.py`) + client grain cache when possible.
- Keep Data Mgmt raw rows + CSV **admin-only** (UI hide + API 403).
- JSON-sanitize NaN/Inf → `null` for any row/record API (`filter_service.df_to_records`, `animals._json_safe`).
- Commit/push only when user asks. Short commit messages.
- Secrets only in local `backend/.env` / Vercel env. Never commit secrets.

NEVER:
- Introduce React/Next unless asked.
- Reintroduce Streamlit as primary UI.
- Use `-r` includes in `api/requirements.txt` (Vercel Python builder breaks).
- Put secrets in `.env.example` or docs. Both `.env.example` and `backend/.env.example` were purged from git history (force-pushed); treat prior secrets as compromised → rotate if still in use.
- Assume KF data year is current calendar year — seed data is **year 2023**.

---

## Stack

| Layer | Implementation |
|-------|----------------|
| UI | `frontend/` static HTML/CSS/JS + Plotly CDN |
| API local | `backend/app/main.py` (mounts frontend, `/` → `/login.html`) |
| API Vercel | `api/light/` (health+auth+filters+summary+grain/charts SQL, slim deps) + `api/index.py` (custom/data/reports/email, full deps) |
| DB | Supabase Postgres; schema `database/001_schema.sql` |
| Auth | Custom JWT HS256 + scrypt; `sessionStorage`: `access_token`, `user` |
| Deploy | `vercel.json` legacy `builds` (python + static); cron `0 23 * * *` → `GET /api/email/process-due` (Vercel Cron is GET-only) |
| Seed | `scripts/seed.py` + root `Data.csv` → farm `KF` ≈ 12117 rows |

Local run:
```
source .venv/bin/activate
# env: backend/.env (DATABASE_URL pooler :6543; URL-encode @ in password as %40)
cd backend && uvicorn app.main:app --reload --port 8000
# open http://localhost:8000/login.html
```

API base (`frontend/js/api.js`): port 8000 → `/api`; other local ports → `http://localhost:8000/api`; prod → `/api`.

---

## Accounts / roles

| user | pass | is_admin | effects |
|------|------|----------|---------|
| admin | admin123 | true | EID filter, Data Mgmt, full rows |
| owner | owner123 | true | same as admin |
| user | user123 | false | EID → `*****`; no Data Mgmt tab; `/data/query` rows+CSV 403 |

Farm access via `assert_farm_access`. Default farm_id `KF` (`?farm=` or first user farm).

---

## Data facts (KF)

- `GET /api/filters/choices?farm_id=KF` → `years:[2023]`, `max_year:2023`, `total_records≈12117`
- Wrong year (e.g. 2025) → empty filters/table (not a crash)
- Null numerics are common; unsanitized NaN → FastAPI 500 `json.dumps` failure on Data Mgmt

Measures (dropdown): `finalpweight`, `finalgrowthpbs`, `methane`, `animalvalue`, `animalprod`, `carcassweight`, `feedintakekgd`

Core dims: `date`, `eid`, `sex`, `breed`, `treatment`, `mob` (`treatment` null display = `"No Treatment"`)

---

## Request data path

```
Browser → /api/* → routers
  ├─ charts/summary/count → sql_agg.py (preferred)
  └─ data rows, cohorts, custom chart, reports → filter_service pandas
       (farm DF cached ~180s in FilterService._FARM_DF_CACHE)
```

Filter payload shape (`FilterState` / `getFilters()`):
`farm_id, year, month, day, sex[], treatment[], breed[], mob[], eid[], measure`
Multi-select `"Overall"` = no filter on that dim. Non-admin eid forced Overall.

---

## UI map

Entry: `frontend/dashboard.html` tabs → `PAGE_RENDERERS` → `frontend/js/pages/*.js`
Sidebar: `frontend/js/filters.js` (debounce, choices, count badge via `POST /data/query` `include_rows:false`)
Saved views: `frontend/js/saved-views.js` (localStorage)

| page id | file | notes |
|---------|------|-------|
| summary | summary.js | shares grain cache w/ timeseries via `ensureScopeGrain` |
| timeseries | timeseries.js | `/charts/timeseries-grain` year×measure cache; month/day + dims recompute client-side; other measures prefetched; EID → refetch |
| distributions | distributions.js | `/charts/distribution` |
| cohorts | cohorts.js | `/cohorts/analyze` + CSV |
| data-management | data-management.js | ADMIN ONLY; paginated table + CSV |
| customise | customise.js | `/charts/custom`; rules in `customizechart.md` NOT fully enforced |
| reports | reports.js | PDF/HTML generate; send-now; schedules |

Data Mgmt behavior:
- page size ~20 (fit viewport 10–40)
- UI: prev/next, page number window, jump-to
- resets page on filter change (`resetDataManagementPage`)
- `POST /data/query` `{include_rows:true, page, page_size}`; `build_groups=False`
- `GET /data/export.csv` full filtered set
- columns fixed in `animals.DATA_MGMT_COLUMNS`

---

## API (all under `/api`)

```
GET  /health
POST /auth/login | GET /auth/me | PUT /auth/password | PUT /auth/username
GET  /filters/choices?farm_id=
POST /data/query          # include_rows false = count (all); true = admin rows
GET  /data/export.csv     # admin
POST /summary/stats
POST /charts/timeseries | /timeseries-grain | /distribution | /custom
POST /cohorts/analyze | GET /cohorts/export.csv
POST /reports/generate | /reports/chart.png
GET|POST|PATCH|DELETE /email/schedules* | POST /email/send-now | POST /email/process-due
/admin/* farms upload users | /farms/*
```

Schemas: `backend/app/models/schemas.py`

---

## File ownership (edit targets)

```
api/light/index.py + api/light/requirements.txt     # slim health/auth/filters
api/index.py, api/requirements.txt, vercel.json     # deploy/cold-start (heavy)
backend/app/main.py                                 # local server+static
backend/app/config.py, db.py, auth/*                # config/auth
backend/app/routers/*.py                            # HTTP
backend/app/services/sql_agg.py                     # SQL charts/summary/count (perf)
backend/app/services/filter_service.py              # pandas load/filter/group/records
backend/app/services/data_service.py                # thin wrapper
backend/app/services/chart_service.py               # cohorts helpers
backend/app/services/report_generator.py            # PDF/HTML (+ matplotlib axes)
backend/app/services/email_service.py               # SMTP; EMAIL_DRY_RUN short-circuit
backend/app/utils/anonymize.py
frontend/js/api.js|auth.js|filters.js|saved-views.js|utils.js
frontend/js/pages/*.js | dashboard.html | login.html | css/*
database/001_schema.sql | scripts/seed.py | Data.csv
customizechart.md                                   # open customise product rules
admin-cli/admin.py
```

---

## Finished work (do not redo)

- Vercel: slim `api/light/` for health/auth/filters; heavy `api/index.py` for charts/data/reports; Hobby daily email cron; static routes; `/`→login; keep-warm via external cron (see VERCEL_DEPLOYMENT.md); enable Fluid Compute in project settings
- Perf: SQL agg path; timeseries grain + client cache; summary KPIs are observation-level (not median-of-daily-means); slim login CSS; auth path avoids pandas
- Reports: multi-chart PDF/HTML; readable date axes; no bogus double units
- Email: surface SMTP/dry-run errors; validate recipient; real send needs `EMAIL_DRY_RUN=false` + SMTP app password on Vercel
- Data Mgmt: admin-only UI+API; pagination+jump; CSV; NaN JSON fix
- Secrets: `.env.example` / `backend/.env.example` removed from all git history (force-push); gitignored; local placeholder only

History tip (SHAs rewritten after filter-repo): `ebb7b90` NaN fix; `c6f8712` data mgmt admin. Older SHA citations in docs may be stale.

---

## Open / next work

### 1. Customise chart rules — NOT implemented (`customizechart.md`)
Current: generic groupby+agg in `routers/charts.py` `/custom` + `customise.js`.
Required:
- **line**: X must be Date
- **bar**: if `group_by` set and ≠ x → clustered multi-bar (clusters = group_by values)
- **scatter**: no group_by / no aggregation

### 2. Optional: Data Mgmt SQL LIMIT/OFFSET
Still loads filtered DF in pandas then slices; OK ~12k rows; can timeout under cold Vercel.

### 3. Email prod
If “sent” but no mail: check Vercel `EMAIL_DRY_RUN`, SMTP app password, function logs.
Cron path must accept **GET** (Vercel Cron) + `Authorization: Bearer $CRON_SECRET` and/or `x-vercel-cron: 1`.

### 4. Spec drift
Ignore Streamlit deploy paths. Prefer code + this file over blueprint markdown when conflict.

---

## Env vars (names only)

`DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRY_HOURS`, `CORS_ORIGINS`,
`EMAIL_PROVIDER`, `EMAIL_FROM`, `EMAIL_DRY_RUN`,
`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS`,
`CRON_SECRET`, `DEFAULT_TIMEZONE`, `DEFAULT_FARM_ID`, `LOGOS_LOCAL_PATH`
(+ optional `SUPABASE_*` if used)

Local secrets file: `backend/.env` (gitignored). Template: local `.env.example` (gitignored, placeholders).

---

## Debug playbook

| Symptom | Likely cause |
|---------|----------------|
| Data Mgmt empty | year ≠ 2023 OR non-admin OR filters exclude all |
| Data Mgmt 500 / “Request failed” | NaN in JSON (should be fixed; re-check df_to_records) |
| Login slow/cold on Vercel | fat Python cold start OR functions not in `syd1` (DB in Sydney) — confirm `/api/health` `"tier":"light"`; `vercel.json` `regions:[syd1]`; Fluid + 5‑min keep-warm |
| Charts slow after checkbox | grain cache miss; EID filter forces server path |
| Email no delivery | `EMAIL_DRY_RUN=true` |
| Vercel python build fail | nested `-r` in requirements |
| Empty API from :3000 frontend | API not on :8000 / CORS |

Verify:
```
curl -s localhost:8000/api/health
# login admin → Data Mgmt rows for year 2023; user → no Data Mgmt tab
```

---

## Update rule

When architecture, auth rules, deploy entry, or open tasks change, update this file in the same PR/commit as the code change.
