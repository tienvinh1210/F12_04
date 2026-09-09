# TEAM_COMMIT_GUIDE.md — 3 contributors (Sydney Uni repo)

**Read this before you write a single commit.**  
You already have the **initial project report** — this guide maps that report’s features onto **exact files**, **exact branches**, and **exact commit rules** so three people contribute equally and merge cleanly into one codebase.

| | |
|--|--|
| **Course repo (contribute here)** | https://github.sydney.edu.au/tdan0407/F12_04_2026.git |
| **Working product / deploy reference** | https://github.com/tienvinh1210/F12_04.git · https://f12-04.vercel.app/ |
| **Product** | Livestock feedlot analytics dashboard (farm `KF` = Killara Feedlot) |
| **Stack** | FastAPI + static HTML/JS + Plotly + Supabase Postgres + Vercel |
| **Admin login** | `F12_04` / `COMP3988_2026` |
| **Viewer login** | `user` / `user123` (no Data Mgmt; EIDs masked) |

---

## 0. Absolute rules (all three people)

1. **One person = one branch.** Never push to someone else’s branch.
2. **Only commit files listed under YOUR section.** If Git stages anything else, `git restore --staged <file>` before commit.
3. **Never commit secrets:** `backend/.env`, `.env`, SMTP passwords, JWT secrets, Supabase keys, `Data.csv` if your clone already excludes it — check `.gitignore`.
4. **Never reformat** a whole file you did not meaningfully change (auto-format wars = merge hell).
5. **Do not edit “shared conflict magnets”** unless the whole team agrees in writing first (see §5).
6. **Commit often, small, and named.** Prefer 5 small commits over 1 giant dump so markers can see *your* work.
7. **Pull `main` before every PR.** Resolve conflicts only in *your* files; if the conflict is in a shared file, stop and message the team.
8. **PR target is always `main`.** Title format: `U1 analytics: short description` / `U2 data: …` / `U3 platform: …`.

---

## 1. Repo layout you will use

```text
main                        ← integration branch (merge PRs here)
contrib/core-analytics      ← User 1
contrib/data-customise      ← User 2
contrib/auth-reports        ← User 3
```

### First-time clone (each person)

```bash
git clone https://github.sydney.edu.au/tdan0407/F12_04_2026.git
cd F12_04_2026
git checkout contrib/core-analytics    # User 1 only
# OR
git checkout contrib/data-customise    # User 2 only
# OR
git checkout contrib/auth-reports      # User 3 only
```

### Daily loop

```bash
git checkout contrib/<your-branch>
git fetch origin
git merge origin/main          # bring in teammates’ merged work
# …edit only YOUR files…
git status                     # verify no foreign files
git add <only-your-files>
git commit -m "U1 analytics: …"
git push -u origin HEAD
# open Pull Request → main on github.sydney.edu.au
```

### Local run (everyone)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
# create backend/.env from teammate secrets share (never commit it)
cd backend && uvicorn app.main:app --reload --port 8000
# open http://localhost:8000/login.html
```

Seed year for KF sample data is **2023** (not the current calendar year).

---

## 2. How the three modules map to the initial report

Use this as the “who owns which report section” cheat sheet.

| Initial-report theme | Owner | Dashboard tab / capability |
|----------------------|-------|----------------------------|
| Login, roles, admin vs viewer, EID privacy | **User 3** | Login page; JWT; admin routes |
| Global filters, saved views, record counts | **User 1** | Sidebar filters |
| Summary statistics / KPI cards | **User 1** | Summary Stats |
| Time-series charts | **User 1** | Time Series |
| Distributions / histograms | **User 1** | Distributions |
| Raw data table + CSV export (admin) | **User 2** | Data Mgmt |
| Cohort analysis | **User 2** | Cohorts |
| Custom / free-form charts | **User 2** | Customise |
| PDF/HTML reports + scheduled email | **User 3** | Reports + cron |
| Deploy / hosting notes | **User 3** | `vercel.json`, deploy docs |

**Equality note:** User 1 already has the largest existing code surface (`sql_agg.py`, timeseries grain cache). User 2 owns the largest **remaining product gap** (`customizechart.md` rules). User 3 owns auth + reports/email + deploy verification. Contribution is judged by **meaningful commits on your paths**, not by rewriting someone else’s module.

---

## 3. User 1 — `contrib/core-analytics`

### Mission
Own the **filter sidebar** and the three “core analytics” pages so month/day/measure changes stay fast and KPIs match observation-level aggregates described in the report.

### Branch
`contrib/core-analytics`

### Files you MAY commit (whitelist)

**Frontend**

```text
frontend/js/filters.js
frontend/js/saved-views.js
frontend/js/pages/summary.js
frontend/js/pages/timeseries.js
frontend/js/pages/distributions.js
```

**Backend**

```text
backend/app/routers/filters.py
backend/app/routers/summary.py
backend/app/routers/charts.py          # timeseries + distribution (+ grain) ONLY
backend/app/services/sql_agg.py
backend/app/services/choices_service.py
backend/app/services/labels.py
backend/app/services/summary_service.py
```

**Tests you should ADD (new files OK)**

```text
backend/tests/test_sql_agg.py
backend/tests/test_filters_api.py     # optional
```

**Docs you MAY touch (append only; no rewriting other people’s sections)**

```text
TESTING.md          # only analytics test bullets
HANDOFF.md          # only “Open / next work” bullets that are analytics-related
```

### Files you must NEVER commit

Anything under User 2 or User 3 lists, plus:

```text
frontend/js/pages/data-management.js
frontend/js/pages/cohorts.js
frontend/js/pages/customise.js
frontend/js/pages/reports.js
frontend/js/auth.js
frontend/login.html
backend/app/routers/animals.py
backend/app/routers/cohorts.py
backend/app/routers/auth.py
backend/app/routers/admin.py
backend/app/routers/reports.py
backend/app/routers/email_schedules.py
backend/app/services/filter_service.py
backend/app/services/report_generator.py
backend/app/services/email_service.py
vercel.json
api/**
scripts/seed.py
database/001_schema.sql
```

### What “good commits” look like for User 1

Land work as **separate commits** (examples — adapt messages; keep `U1 analytics:` prefix):

| # | Commit message | Files typically included | What the commit must demonstrate |
|---|----------------|--------------------------|----------------------------------|
| 1 | `U1 analytics: add sql_agg tests for KF 2023 overall KPIs` | `backend/tests/test_sql_agg.py` | Overall mean/median/min/max/count for `finalpweight` under Overall filters |
| 2 | `U1 analytics: document grain cache month/day client filter` | `frontend/js/pages/timeseries.js` and/or `summary.js` (comments or small clarity fix) | Year×measure grain still fetched once; month/day applied client-side |
| 3 | `U1 analytics: harden empty distribution / zero-row UI` | `distributions.js` (+ optional tiny CSS via injected HTML only) | No blank crash when filters exclude all rows |
| 4 | `U1 analytics: saved-views load restores multi-select Overall` | `saved-views.js`, maybe `filters.js` | Save → reload page → same filter state |
| 5 | `U1 analytics: bootstrap choices+summary regression notes` | `TESTING.md` or `filters.py` if fixing a real bug | `/filters/bootstrap` (if present) or choices+summary path still works |

### Acceptance checklist (User 1 — before opening PR)

- [ ] Login as admin → Summary Stats shows KPI cards for year **2023**
- [ ] Change **month** then **day** then **measure** — charts update without multi-second freezes when warm
- [ ] Time Series still uses `/charts/timeseries-grain` year×measure cache behaviour
- [ ] Distributions plot for at least one measure
- [ ] Saved view save/load/delete works
- [ ] `git diff --name-only origin/main...HEAD` shows **only** whitelist paths (+ your new tests)
- [ ] Non-admin (`user`) still works on Summary/Time Series/Distributions (EID not required)

### Suggested PR title
`U1 analytics: core filters + summary/timeseries/distributions`

---

## 4. User 2 — `contrib/data-customise`

### Mission
Own **admin Data Management**, **Cohorts**, and **Customise Chart**. Your headline unfinished report item is enforcing `customizechart.md` rules end-to-end (backend + UI).

### Branch
`contrib/data-customise`

### Files you MAY commit (whitelist)

**Frontend**

```text
frontend/js/pages/data-management.js
frontend/js/pages/cohorts.js
frontend/js/pages/customise.js
```

**Backend**

```text
backend/app/routers/animals.py
backend/app/routers/cohorts.py
backend/app/services/filter_service.py
backend/app/services/chart_service.py
backend/app/services/data_service.py
```

**Customise chart endpoint (important)**  
Today `/charts/custom` lives inside `backend/app/routers/charts.py` together with timeseries/distribution (User 1’s file).

**Do this without stealing User 1’s file long-term:**

1. Prefer extracting customise into a **new** file you own, e.g.:
   - `backend/app/routers/custom_charts.py`  ← YOU create & own forever
2. In a **tiny coordinated PR** (or ask User 3 / lead), register it in `backend/app/main.py` and, if needed, `api/index.py`.
3. Until extraction is merged, you may temporarily edit **only the `/custom` function** inside `charts.py` — never rewrite timeseries/distribution handlers. Prefer extraction in your first commit.

**Product rules doc**

```text
customizechart.md
```

**Tests**

```text
backend/tests/test_filter_service.py     # already exists — extend
backend/tests/test_custom_charts.py      # new — you create
backend/tests/test_animals_admin.py      # new — optional
```

**Docs (append only)**

```text
TESTING.md
HANDOFF.md          # customise / data-mgmt open items only
```

### Files you must NEVER commit

```text
frontend/js/filters.js
frontend/js/pages/summary.js
frontend/js/pages/timeseries.js
frontend/js/pages/distributions.js
frontend/js/pages/reports.js
frontend/js/auth.js
backend/app/services/sql_agg.py
backend/app/routers/filters.py
backend/app/routers/summary.py
backend/app/routers/auth.py
backend/app/routers/reports.py
backend/app/routers/email_schedules.py
backend/app/services/report_generator.py
backend/app/services/email_service.py
vercel.json
scripts/seed.py
```

### Required product behaviour (`customizechart.md`)

Implement and prove with commits:

| Chart type | Rule you must enforce |
|------------|------------------------|
| **line** | X axis **must be Date** — reject or disable other X choices |
| **bar** | If `group_by` is set and ≠ X → **clustered multi-bar** (clusters = group_by values) |
| **scatter** | **No** group_by / **no** aggregation |

### What “good commits” look like for User 2

| # | Commit message | Files | Must demonstrate |
|---|----------------|-------|------------------|
| 1 | `U2 data: extract /charts/custom into custom_charts router` | new `custom_charts.py` + minimal `main.py` registration (coord) | Same URL still works; User 1’s timeseries routes untouched |
| 2 | `U2 data: enforce line chart X=Date rule` | `custom_charts.py`, `customise.js` | Non-date X blocked with clear error/toast |
| 3 | `U2 data: clustered multi-bar when group_by ≠ x` | `custom_charts.py`, `customise.js` | Plotly traces match clustered behaviour |
| 4 | `U2 data: scatter disables group/agg` | `customise.js` (+ backend validation) | UI greys out group/agg; API rejects if forced |
| 5 | `U2 data: keep Data Mgmt admin-only + NaN-safe rows` | `animals.py`, `data-management.js`, `filter_service.py` | Non-admin 403; no JSON 500 on null numerics |
| 6 | `U2 data: cohorts analyze + CSV smoke test` | `cohorts.js` / `cohorts.py` / tests | Analyze returns rows; export downloads |
| 7 | `U2 data: optional SQL LIMIT/OFFSET for Data Mgmt pages` | `animals.py` (and helpers) | Page 2 does not require loading entire filtered frame if you implement this |

### Acceptance checklist (User 2)

- [ ] Admin sees Data Mgmt; `user` does **not** (tab hidden + API 403)
- [ ] Data Mgmt pagination + jump-to still works for year 2023
- [ ] CSV export works for admin
- [ ] Cohorts analyze + CSV export work
- [ ] Customise: line/bar/scatter rules match `customizechart.md`
- [ ] No NaN → FastAPI JSON 500 on Data Mgmt
- [ ] `git diff --name-only origin/main...HEAD` is whitelist-only (plus agreed `main.py` one-liner for router include)

### Suggested PR title
`U2 data: data mgmt + cohorts + customise chart rules`

---

## 5. User 3 — `contrib/auth-reports`

### Mission
Own **authentication / roles / admin**, **Reports (PDF/HTML)**, **scheduled email**, and **deployment wiring**. You are the platform person from the initial report’s “access control + delivery” sections.

### Branch
`contrib/auth-reports`

### Files you MAY commit (whitelist)

**Auth / login / admin**

```text
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
database/001_schema.sql          # users / farms / access tables only — do not redesign animal_data casually
```

**Reports / email**

```text
frontend/js/pages/reports.js
backend/app/routers/reports.py
backend/app/services/report_generator.py
backend/app/routers/email_schedules.py
backend/app/services/email_service.py
scripts/test_email.py
backend/tests/test_email_service.py
```

**Deploy**

```text
vercel.json
api/index.py
api/requirements.txt
api/light/index.py
api/light/requirements.txt
VERCEL_DEPLOYMENT.md
DEPLOYMENT.md
EMAIL_SYSTEM.md
AUTH_AND_ROLES.md
ADMIN_OPERATIONS.md
```

**Tests you should ADD**

```text
backend/tests/test_auth.py
backend/tests/test_email_cron.py
```

### Files you must NEVER commit

```text
frontend/js/filters.js
frontend/js/pages/summary.js
frontend/js/pages/timeseries.js
frontend/js/pages/distributions.js
frontend/js/pages/data-management.js
frontend/js/pages/cohorts.js
frontend/js/pages/customise.js
backend/app/services/sql_agg.py
backend/app/services/filter_service.py
backend/app/routers/charts.py
backend/app/routers/animals.py
backend/app/routers/cohorts.py
customizechart.md
```

### Shared conflict magnets (ask before editing)

These break merges if two people touch them. **Default: do not edit.** If User 2 needs a router include, User 3 may merge that one-line change into `main` via a tiny PR, or approve User 2’s PR that only adds:

```python
app.include_router(custom_charts.router, prefix="/api/charts", tags=["charts"])
```

| File | Why dangerous |
|------|----------------|
| `frontend/dashboard.html` | All tabs + script tags |
| `frontend/js/api.js` | Every page’s fetch wrapper |
| `frontend/js/utils.js` | Shared helpers |
| `frontend/css/components.css` | Global layout |
| `frontend/css/pages.css` | All pages |
| `frontend/css/variables.css` | Theme tokens |
| `backend/app/main.py` | Router registration |
| `backend/app/models/schemas.py` | All request bodies |
| `backend/app/constants.py` | Measures / dims |
| `backend/app/db.py` | Connection pool |
| `backend/app/config.py` | Settings |

**Schema exception:** you may append fields to a model **you own** (`LoginRequest`, report/email schemas). Do not reorder unrelated classes. User 1 owns timeseries/distribution filter request fields. User 2 owns `CustomChartRequest`.

### What “good commits” look like for User 3

| # | Commit message | Files | Must demonstrate |
|---|----------------|-------|------------------|
| 1 | `U3 platform: auth login/me tests for admin vs viewer` | `test_auth.py` | 200 for `F12_04`; 401 bad password; `user` has `is_admin:false` |
| 2 | `U3 platform: EID anonymize helper covered by test` | `anonymize.py` + test | Non-admin path masks EIDs |
| 3 | `U3 platform: email process-due accepts GET + cron auth` | `email_schedules.py` + test | Matches Vercel Cron GET behaviour |
| 4 | `U3 platform: surface SMTP/dry-run errors on send-now` | `email_service.py`, `reports.js` if needed | UI/API shows why send failed when `EMAIL_DRY_RUN=true` |
| 5 | `U3 platform: report PDF/HTML generate smoke path` | `report_generator.py` / `reports.py` | Generate returns file/bytes without crash for KF 2023 filters |
| 6 | `U3 platform: document keep-warm + Fluid + syd1` | `VERCEL_DEPLOYMENT.md` | Accurate Hobby keep-warm instructions |
| 7 | `U3 platform: seed keeps F12_04 admin credentials` | `scripts/seed.py` | Re-seed does not recreate obsolete `admin`/`admin123` |

### Acceptance checklist (User 3)

- [ ] `POST /api/auth/login` works for `F12_04` / `COMP3988_2026`
- [ ] `user` / `user123` cannot open Data Mgmt (UI + API)
- [ ] Reports tab can generate PDF or HTML without 500
- [ ] `GET /api/email/process-due` authorised path documented and tested
- [ ] `/api/health` on light tier still returns ok (do not break `api/light`)
- [ ] No secrets in any committed file
- [ ] Diff is whitelist-only

### Suggested PR title
`U3 platform: auth + reports + email + deploy`

---

## 6. Merge order & conflict playbook

Preferred merge order if all three open PRs the same day:

1. **User 3** (auth/platform) — fewer analytics conflicts  
2. **User 1** (analytics)  
3. **User 2** (data/customise; may need `main.py` include)

Any order is fine **if whitelists were respected**.

| Conflict path | Who resolves |
|---------------|--------------|
| `filters.js`, `sql_agg.py`, `timeseries.js`, `summary.js` | User 1 |
| `animals.py`, `customise.js`, `filter_service.py`, `custom_charts.py` | User 2 |
| `auth.js`, `email_schedules.py`, `report_generator.py`, `vercel.json`, `seed.py` | User 3 |
| `dashboard.html`, `api.js`, `schemas.py`, `main.py` | **Stop.** One coordinated commit on `main`, then everyone `git merge origin/main` |

---

## 7. Proving “equal contribution” to markers

Markers often run something like:

```bash
git log --author="<your-name>" --name-only --pretty=format: -- contrib/  # or after merge:
git log main --author="<your-name>" --name-only
```

So:

1. Use **your GitHub.sydney.edu.au identity** on commits (`git config user.name` / `user.email` for this repo only).
2. Keep commits on **your whitelist paths**.
3. Prefer **feature commits** over “fix typos in README” padding.
4. Do **not** mass-reformat User 1’s `sql_agg.py` to pad lines.

Rough equal “story” for the report:

| User | Existing heavy code | New value you add |
|------|---------------------|-------------------|
| U1 | Filters + SQL analytics | Tests + empty states + grain/cache correctness |
| U2 | Data/cohorts shell | **Customise rules** + admin data safety + optional SQL paging |
| U3 | Auth + reports/email | Auth tests + cron/email reliability + deploy docs |

---

## 8. Pre-commit self-audit (copy/paste)

Run before every push:

```bash
# What am I about to push vs main?
git fetch origin
git diff --name-only origin/main...HEAD

# Staged files right now
git diff --cached --name-only
```

If any path is **not** on your whitelist → unstage it:

```bash
git restore --staged path/to/foreign/file
git restore path/to/foreign/file   # if you accidentally edited it
```

---

## 9. Quick reference card

| | User 1 | User 2 | User 3 |
|--|--------|--------|--------|
| Branch | `contrib/core-analytics` | `contrib/data-customise` | `contrib/auth-reports` |
| Tabs | Summary, Time Series, Distributions + Filters | Data Mgmt, Cohorts, Customise | Login, Reports (+ email/deploy) |
| Key backend | `sql_agg.py`, `charts.py` (non-custom) | `animals.py`, `filter_service.py`, custom charts | `auth/*`, `email_*`, `report_*` |
| Headline deliverable | Fast correct analytics | `customizechart.md` enforced | Auth + email cron + deploy |
| Commit prefix | `U1 analytics:` | `U2 data:` | `U3 platform:` |

---

## 10. What not to do (common failures)

- Pushing to `main` directly without PR  
- Committing `backend/.env`  
- “Helping” by editing another user’s page JS  
- Rewriting the whole app in React/Next/Streamlit  
- Changing KF seed year assumptions without team agreement  
- Force-pushing `main`  
- One 5,000-line commit the night before deadline  

---

## 11. Done definition for the whole team

The three PRs are successfully merged into `main` when:

1. Admin can log in and use **all seven tabs** without 500s on year 2023 KF data  
2. Viewer cannot access Data Mgmt  
3. Customise obeys line/bar/scatter rules from the report / `customizechart.md`  
4. Email process-due still accepts **GET** for Vercel Cron  
5. `git log main` shows clear `U1` / `U2` / `U3` commit prefixes on distinct file sets  

If anything in this guide conflicts with classroom instructions, **classroom instructions win** — update this file in a tiny docs-only commit on `main`.
