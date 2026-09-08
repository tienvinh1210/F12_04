# Team split — 4 modules, merge-safe

Four people, four Git branches, **exclusive file ownership**. Start from the same `main`. Merge with pull requests back into `main`. Do not edit another person’s files.

```
repo: https://github.com/tienvinh1210/F12_04.git
base: main
```

| Person | Branch | Module |
|--------|--------|--------|
| P1 | `module/auth-admin` | Login, JWT, roles, admin/farms, seed |
| P2 | `module/core-analytics` | Filters, summary, time series, distributions |
| P3 | `module/data-customise` | Data Mgmt, cohorts, customise charts |
| P4 | `module/reports-email` | Reports, scheduled email, Vercel deploy |

Checkout:

```bash
git fetch origin
git checkout module/auth-admin        # P1
git checkout module/core-analytics    # P2
git checkout module/data-customise    # P3
git checkout module/reports-email     # P4
```

---

## How merges stay easy

1. **Only commit files listed under your module.** If you need a shared file, stop and coordinate (see Shared files).
2. **Do not reformat** whole files you do not own (`black`/`prettier` on someone else’s tree = guaranteed conflicts).
3. **Do not rebase other people’s branches.** `git pull origin main` then merge your PR.
4. **Merge order** (if PRs land the same week): P1 → P2 → P3 → P4. Any order works if ownership was respected.
5. **One PR per module.** Title: `P1 auth-admin: …` so history is obvious for contribution.

If two people must touch the same file, one person makes a tiny PR to `main` first; the others `git pull origin main`.

---

## Shared files (do not own — ask first)

These are the conflict magnets. **Default: do not edit.**

| File | Why |
|------|------|
| `frontend/dashboard.html` | All tabs + script tags |
| `frontend/js/api.js` | Every page fetch |
| `frontend/js/utils.js` | Shared helpers |
| `frontend/css/components.css` | Global layout |
| `frontend/css/pages.css` | All page styles |
| `frontend/css/variables.css` | Theme |
| `backend/app/main.py` | Router registration |
| `backend/app/models/schemas.py` | All request bodies |
| `backend/app/constants.py` | Measures / dims |
| `vercel.json` | P4 owns this; others never |
| `api/light/index.py` | P1 + P2 routes; P4 deploys |
| `HANDOFF.md` | Append a bullet under your module only |

**Allowed exception:** append a field to *your* schema class in `schemas.py` (do not reorder other classes). P3 owns `CustomChartRequest`. P2 owns `TimeseriesRequest` / `DistributionRequest` / `FilterState` filter fields.

---

## P1 — `module/auth-admin`

**Owns (edit freely)**

```
frontend/login.html
frontend/css/login.css
frontend/js/auth.js
backend/app/auth/dependencies.py
backend/app/auth/passwords.py
backend/app/routers/auth.py
backend/app/routers/admin.py
backend/app/routers/farms.py
backend/app/utils/anonymize.py
admin-cli/admin.py
scripts/seed.py
database/001_schema.sql          # users / farms / user_farm_access only
AUTH_AND_ROLES.md
ADMIN_OPERATIONS.md
```

**Do not edit:** `sql_agg.py`, page JS under `frontend/js/pages/`, email/report files, `vercel.json`.

**Scoped work (keep size similar to others)**

- Tests: `backend/tests/test_auth.py` — login 200/401, `/auth/me`, non-admin cannot hit admin routes, EID anonymize
- Login UX: errors, disabled button, “signing in” already exists — polish only in login CSS/JS
- Admin: user create / password change / farm access (`routers/admin.py`) — document in `ADMIN_OPERATIONS.md`
- Seed: keep `F12_04` / `COMP3988_2026` working; do not invent a second admin username without the team

**Done when:** `user` cannot see Data Mgmt tab (already wired; do not break it); admin login still returns `is_admin: true`.

---

## P2 — `module/core-analytics`

**Owns**

```
frontend/js/filters.js
frontend/js/pages/summary.js
frontend/js/pages/timeseries.js
frontend/js/pages/distributions.js
frontend/js/saved-views.js
backend/app/routers/filters.py
backend/app/routers/summary.py
backend/app/routers/charts.py          # timeseries + distribution only
backend/app/services/sql_agg.py
backend/app/services/choices_service.py
backend/app/services/labels.py
backend/app/services/summary_service.py
```

**Do not edit:** `custom_charts.py`, `customise.js`, `animals.py`, `filter_service.py`, reports/email, login.

**Scoped work**

- Tests: `backend/tests/test_sql_agg.py` — overall summary KPIs for KF 2023 `finalpweight`; grain ignores month/day
- Keep year×measure grain cache behaviour in `timeseries.js` / `summary.js`
- Distributions: empty-state + loading (small UI, your CSS only if you add a page-local class in the JS-injected HTML, not `pages.css` unless coordinated)
- Saved views: persist/load without breaking filter debounce

**Done when:** changing month/day/measure still feels fast; Summary first paint still uses `/filters/bootstrap` where present.

---

## P3 — `module/data-customise`

**Owns**

```
frontend/js/pages/data-management.js
frontend/js/pages/cohorts.js
frontend/js/pages/customise.js
backend/app/routers/animals.py
backend/app/routers/cohorts.py
backend/app/routers/custom_charts.py
backend/app/services/filter_service.py
backend/app/services/chart_service.py
backend/app/services/data_service.py
backend/tests/test_filter_service.py
customizechart.md
```

**Do not edit:** `sql_agg.py`, `charts.py` (timeseries), `auth.js`, reports/email.

**Scoped work (largest remaining product gap — balances P2’s larger existing LOC)**

- Implement `customizechart.md` in `custom_charts.py` + `customise.js`:
  - **line:** X must be Date (reject / disable otherwise)
  - **bar:** if `group_by` set and ≠ x → clustered multi-bar
  - **scatter:** no group_by / no aggregation
- Data Mgmt: optional SQL `LIMIT/OFFSET` instead of pandas-then-slice (HANDOFF open item); keep admin-only + NaN → `null`
- Cohorts: keep analyze + CSV; add tests around empty filter

**Done when:** customise rules match `customizechart.md`; Data Mgmt still 403 for non-admin; no NaN JSON 500s.

---

## P4 — `module/reports-email`

**Owns**

```
frontend/js/pages/reports.js
backend/app/routers/reports.py
backend/app/services/report_generator.py
backend/app/routers/email_schedules.py
backend/app/services/email_service.py
backend/tests/test_email_service.py
scripts/test_email.py
api/index.py
api/requirements.txt
api/light/index.py               # deploy wiring only; do not rewrite auth/analytics
api/light/requirements.txt
vercel.json
EMAIL_SYSTEM.md
VERCEL_DEPLOYMENT.md
DEPLOYMENT.md
```

**Do not edit:** page JS for summary/timeseries/data/customise, `sql_agg.py`, seed passwords.

**Scoped work**

- Tests: process-due accepts GET + cron auth; send-now surfaces SMTP/dry-run errors
- Reports: keep PDF/HTML; fix any broken date axes; do not pull pandas into `api/light`
- Deploy: Fluid / syd1 / keep-warm docs stay accurate; Hobby cron remains GET `/api/email/process-due`
- Optional: document cron-job.org keep-warm (do not require a paid host)

**Done when:** `GET /api/email/process-due` still works on Vercel Cron; `/api/health` on light still `"tier":"light"`; custom charts still hit heavy `api/index.py`.

---

## Shared runtime (read, don’t rewrite)

| Layer | Owner for *changes* |
|-------|---------------------|
| `backend/app/db.py`, `config.py` | P4 for pool/timeouts; others read-only |
| `backend/app/auth_app.py` | unused / leftover — leave it |
| `frontend/js/api.js` | freeze unless all four agree |
| `Data.csv` | nobody — too large; seed only via P1 `scripts/seed.py` |

---

## Contribution (roughly equal)

Existing code is **not** even by line count (analytics is larger). Equality is:

| Person | Existing module | Extra work to land |
|--------|-----------------|--------------------|
| P1 | Auth/admin/login (~0.7k LOC) | Auth tests + admin/seed docs |
| P2 | Analytics (~2.1k LOC) | sql_agg tests + keep grain cache correct |
| P3 | Data/cohorts (~1.2k LOC) | **Customise chart rules** (main remaining feature) |
| P4 | Reports/email/deploy (~1.1k LOC) | Email/cron tests + deploy docs |

Do not “help” another module to pad commits. Marker can `git log --author` per path.

---

## Daily workflow

```bash
git checkout module/<your-branch>
git pull origin main
# edit only your files
git add <your files>
git commit -m "P2 analytics: …"
git push -u origin HEAD
```

Open a PR into `main`. After merge, others run `git pull origin main`.

---

## Conflict cheat sheet

| If Git says conflict in… | Whose job |
|---------------------------|-----------|
| `filters.js`, `sql_agg.py`, `timeseries.js` | P2 |
| `custom_charts.py`, `customise.js`, `animals.py` | P3 |
| `auth.js`, `login.css`, `seed.py` | P1 |
| `email_schedules.py`, `vercel.json`, `report_generator.py` | P4 |
| `dashboard.html`, `api.js`, `schemas.py` | pause; one tiny coordinated PR |

---

## Local run (everyone)

```
source .venv/bin/activate
cd backend && uvicorn app.main:app --reload --port 8000
# http://localhost:8000/login.html
# admin: F12_04 / COMP3988_2026
```
