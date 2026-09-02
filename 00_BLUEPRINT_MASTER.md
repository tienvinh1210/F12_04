# Master Blueprint — Livestock Dashboard (Python Rebuild)

## 1. Project summary

### Purpose
A web dashboard for **livestock feedlot performance analytics**. Farm managers filter animal records by date, sex, treatment, breed, mob, and (for admins) electronic ID (EID). They view summary KPIs, time series, distributions, cohort rankings, custom charts, data tables, and scheduled email reports.

### Original system (being replaced)
- **R + Shiny** single-page app per farm
- **DuckDB** embedded database per farm (`{farm_id}_data.duckdb`)
- **shinymanager** authentication with scrypt-hashed passwords in DuckDB
- **shinyapps.io** deployment (one app URL per farm)
- **Admin CLI** (Windows `.bat` + R scripts) for CSV upload, backup, deploy

### New system goals
1. **Python backend** — maintainable, testable business logic
2. **HTML/CSS/JS frontend** — modern UI (fix "terrible UI" from original)
3. **Supabase** — single PostgreSQL database, multi-tenant by `farm_id`
4. **Vercel** — static frontend + API (or hybrid architecture)
5. **Feature parity** with all original pages + improved UX

---

## 2. High-level architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        VERCEL (CDN)                              │
│  ┌──────────────────┐    ┌──────────────────────────────────┐   │
│  │  Static HTML/JS  │───▶│  /api/* → Python serverless OR   │   │
│  │  dashboard UI    │    │  external FastAPI (Render/Fly)   │   │
│  └──────────────────┘    └──────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         SUPABASE                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ PostgreSQL  │  │ Auth (opt.)  │  │ Storage (logos, CSVs)  │  │
│  │ + RLS       │  │ or custom JWT│  │                        │  │
│  └─────────────┘  └──────────────┘  └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              Background worker (cron / Supabase Edge / Render)     │
│              Email scheduler — checks due schedules hourly        │
└─────────────────────────────────────────────────────────────────┘
```

### Recommended project structure (to be created by implementer)

```
livestock-dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry
│   │   ├── config.py               # env vars
│   │   ├── db.py                   # Supabase/Postgres client
│   │   ├── auth/
│   │   │   ├── passwords.py        # scrypt verify (compat with old hashes)
│   │   │   └── dependencies.py     # get_current_user
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── animals.py          # filtered data queries
│   │   │   ├── filters.py          # filter choice endpoints
│   │   │   ├── reports.py
│   │   │   ├── admin.py            # CSV upload, farms
│   │   │   └── email_schedules.py
│   │   ├── services/
│   │   │   ├── filter_service.py   # port of filter.R logic
│   │   │   ├── cohort_service.py
│   │   │   ├── summary_service.py
│   │   │   ├── distribution_service.py
│   │   │   ├── report_generator.py
│   │   │   └── email_service.py
│   │   └── models/                 # Pydantic schemas
│   ├── requirements.txt
│   └── tests/
├── frontend/
│   ├── index.html                  # login redirect
│   ├── login.html
│   ├── dashboard.html              # shell with nav + sidebar
│   ├── css/
│   │   ├── variables.css           # design tokens
│   │   ├── components.css
│   │   └── pages.css
│   ├── js/
│   │   ├── api.js                  # fetch wrapper + auth token
│   │   ├── auth.js
│   │   ├── filters.js              # sidebar filter state
│   │   ├── saved-views.js          # localStorage
│   │   ├── pages/
│   │   │   ├── summary.js
│   │   │   ├── timeseries.js
│   │   │   ├── distributions.js
│   │   │   ├── cohorts.js
│   │   │   ├── data-management.js
│   │   │   ├── customise.js
│   │   │   └── reports.js
│   │   └── charts/                 # Plotly helpers
│   └── assets/
│       ├── login_background.png
│       └── logos/                  # per-farm from Supabase Storage
├── admin-cli/                      # optional Python CLI replacing .bat
│   └── admin.py
├── vercel.json
├── .env.example
└── README.md
```

---

## 3. Core domain concepts

### 3.1 Animal record (`animal_data` table)
One row = one animal measurement on one date. Key fields:

| Column | Type | Description |
|--------|------|-------------|
| farm_id | text | Tenant key |
| eid | text | Electronic ID (anonymize for non-admin) |
| date | date | Measurement date |
| breed | text | e.g. "Brahman X" |
| treatment | text nullable | e.g. "Drench"; NULL → "No Treatment" in UI |
| mob | text | Pen/group location |
| sex | text | e.g. Steer, Heifer |
| finalpweight | numeric | Final processed weight (kg) — default measure |
| finalgrowthpbs | numeric | Growth kg/day |
| methane | numeric | g/day |
| animalvalue | numeric | $ |
| animalprod | numeric | production units |
| carcassweight | numeric | kg |
| feedintakekgd | numeric | kg/day |

Full CSV column list in `DATA_MODEL.md`.

### 3.2 Measures (numeric columns for charts/KPIs)
Default selected measure: **`finalpweight`**

| Key | Label | Unit |
|-----|-------|------|
| finalpweight | Final processed weight | kg |
| finalgrowthpbs | Final growth PBS | kg/day |
| methane | Methane production | g/day |
| animalvalue | Animal value | $ |
| animalprod | Animal production rate | units |
| carcassweight | Carcass weight | kg |
| feedintakekgd | Feed intake | kg/day |

### 3.3 Filters (shared sidebar)
All pages except **Customise** use the same filter state:

| Filter | Type | Default | Notes |
|--------|------|---------|-------|
| year | single select | max year in data | **Required** |
| month | single select | "All" | |
| day | single select | "All" | |
| sex | multi-select | "Overall" | "Overall" = no filter |
| treatment | multi-select | "Overall" | includes "No Treatment" for NULL |
| breed | multi-select | "Overall" | |
| mob | multi-select | "Overall" | |
| eid | multi-select | "Overall" | **Admin only** |
| measure | single select | finalpweight | KPI/chart Y-axis |

**Filter semantics:**
- Selecting only `"Overall"` in a multi-select = include all values for that dimension
- Selecting `"Overall"` AND specific values = expand to compare groups (see grouped_data logic in `MIGRATION_FROM_R.md`)
- Empty multi-select resets to `"Overall"`
- Select All / Invert links on each multi-select

### 3.4 Group labels
When comparing groups, build human-readable labels showing only **varying** dimensions:

- Single group, all Overall → `"Overall Average"`
- Multiple groups → `"Sex: Steer | Treatment: Drench"` (only varying cols)

Two label modes:
- **Simplified** (`group`) — for chart legends
- **Full** (`full_group`) — for summary stats cards (always shows all dimensions)

### 3.5 Roles
| Role | is_admin | EID visibility |
|------|----------|----------------|
| admin | true | Real EIDs |
| owner | true | Real EIDs |
| user | false | `*****` |

---

## 4. Dashboard pages (7 tabs)

| # | Tab | Purpose |
|---|-----|---------|
| 1 | Summary Stats | KPI cards per group: Last Day, Last 15 Days, Last Month, Overall |
| 2 | Time Series | Daily mean of measure by group; optional LOESS trend; point size slider |
| 3 | Distributions | Histogram (bins 10–50) + box plot side by side |
| 4 | Cohorts | Top/bottom percentile animals by lifetime average; timeline |
| 5 | Data Management | Sortable/filterable table + CSV download |
| 6 | Customise | User-built chart (line/bar/scatter/area/hist/box) |
| 7 | Reports | Export charts/reports; email now or schedule |

**Global UI elements:**
- Logo header bar (farm logos from storage, sorted by filename)
- Navbar with tab links + Logout
- Left sidebar (350px): all filters + record count + Clear filters + Saved Views
- Empty state when zero records match filters

---

## 5. Design system (improve on original)

### Color tokens (keep brand continuity, polish execution)
```css
--primary: #1B4332;
--primary-light: #2D6A4F;
--primary-dark: #0F2B1F;
--secondary: #5C4033;
--accent: #B08968;
--danger: #7B241C;
--bg: #f4f5f6;
--card-bg: #ffffff;
--text-primary: #2c3e50;
--text-secondary: #6c757d;
--border: #e9ecef;
--gradient-primary: linear-gradient(135deg, #1B4332 0%, #2D6A4F 100%);
```

### Typography
- Font: **Poppins** (Google Fonts)
- Icons: **Font Awesome 6**

### UI improvements over original (required)
1. **Mobile-first responsive** — sidebar collapses to drawer on `<768px`
2. **Loading skeletons** on chart areas (no white flash)
3. **Toast notifications** instead of Shiny notifications
4. **Accessible** form labels, focus states, ARIA on nav
5. **Dark-mode optional** (stretch goal)
6. **Consistent 8px spacing grid**
7. **Better empty states** with filter summary + one-click reset
8. **Debounced filter API calls** (300ms) to reduce server load

---

## 6. Multi-farm tenancy

Original: one DuckDB + one shinyapps.io app per farm.

New: **single deployment**, route by `farm_id`:

- Option A: subdomain `killara.yourdomain.com` → resolves farm
- Option B: path `/dashboard/KF`
- Option C: farm selector after login (if user has access to multiple farms)

Store in `farms` table:
```sql
farm_id, farm_name, slug, is_active, created_at
```

All `animal_data` rows include `farm_id`. Row Level Security (RLS) in Supabase enforces isolation.

User-farm access via `user_farm_access(user_id, farm_id)`.

---

## 7. Admin operations (replace R admin panel)

| Operation | Old | New |
|-----------|-----|-----|
| Upload CSV | `data_upload/{farm_id}_YYYY-MM-DD.csv` + Option 1 | Admin API `POST /api/admin/farms/{farm_id}/upload` or CLI |
| Backup before update | Copy `.duckdb` to `farm_backups/` | `animal_data_snapshots` table or Storage archive |
| Deploy code | rsconnect to shinyapps.io | Git push → Vercel auto-deploy |
| Revert farm | Restore DuckDB backup | Restore from snapshot |
| Manage credentials | CLI Option 6 | Admin UI or `POST /api/admin/users` |
| Farm logos | `farm_logos/{farm_id}/*.png` | Supabase Storage `logos/{farm_id}/` |

CSV naming convention: `{farm_id}_YYYY-MM-DD.csv` (required columns: `eid`, `date`).

On duplicate `(farm_id, eid, date)`: prompt SKIP (default) or OVERWRITE.

---

## 8. Email system

Store schedules in `email_schedules` table (same fields as original DuckDB schema).

**Frequencies:** daily, weekly, monthly, once

**Background job:** run every 15 minutes:
1. Query active schedules where `next_send_at <= now()`
2. Apply stored `report_filters` JSON
3. Generate PDF/HTML report + chart PNGs
4. Send via Resend/SendGrid
5. Update `last_sent`, compute `next_send_at`

Reports page UI: Send Now vs Schedule modes (see `EMAIL_SYSTEM.md`).

---

## 9. Environment variables

```bash
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...        # backend only, never expose to browser
SUPABASE_ANON_KEY=eyJ...                # frontend if using Supabase client directly

# Auth
JWT_SECRET=random-256-bit-string
JWT_EXPIRY_HOURS=24

# Email
RESEND_API_KEY=re_...
EMAIL_FROM=reports@yourdomain.com

# App
FARM_ID=KF                            # if single-tenant deploy
DEFAULT_TIMEZONE=Australia/Sydney
CORS_ORIGINS=https://your-app.vercel.app
```

---

## 10. Key algorithms to port exactly

Implementers **must** match behavior documented in `MIGRATION_FROM_R.md` for:

1. `filter_data()` — base row filtering
2. `build_filtered_reactives()` → `grouped_data` expand.grid logic
3. `create_simplified_group_labels()` and `create_full_group_labels()`
4. `kpi_block()` + `subset_by_window()` — summary stats windows
5. Cohort ranking — per-EID mean, top/bottom percentile cut (10/15/20%)
6. Distribution sampling — cap at 200–500 points per group for performance
7. EID anonymization — replace with `*****` for non-admin on all API responses

---

## 11. Out of scope (unless explicitly requested)

- Porting R unit tests verbatim (write new pytest tests per `TESTING.md`)
- shinyapps.io / rsconnect
- Windows `.bat` admin scripts (replace with Python CLI or web admin)
- DuckDB file format (migrate to Postgres)

---

## 12. Reference: original file → new module map

| Original R file | New Python/JS module |
|-----------------|---------------------|
| `src/global.R` | `backend/app/config.py`, `db.py` |
| `src/filter.R` | `backend/app/services/filter_service.py`, `frontend/js/filters.js` |
| `src/summary_stats.R` | `backend/app/services/summary_service.py`, `frontend/js/pages/summary.js` |
| `src/timeseries_page.R` | `frontend/js/pages/timeseries.js` |
| `src/distribution.R` | `backend/app/services/distribution_service.py` |
| `src/cohorts_page.R` | `backend/app/services/cohort_service.py` |
| `src/customise.R` | `frontend/js/pages/customise.js` |
| `src/report_page.R` | `backend/app/routers/reports.py` |
| `src/report_generator.R` | `backend/app/services/report_generator.py` |
| `src/email_automation.R` | `backend/app/services/email_service.py` |
| `src/ui.R` | `frontend/dashboard.html`, `css/*` |
| `src/server.R` | `backend/app/main.py` + page JS modules |
| `admin_scripts/*` | `admin-cli/admin.py` + `routers/admin.py` |
| `farms.csv` | `farms` Supabase table |

---

## 13. First message for a new AI chat

Copy-paste this to start implementation:

> Build the Livestock Dashboard using the COMP3888 blueprint in `/Downloads/COMP3888`. Read `00_BLUEPRINT_MASTER.md` and `IMPLEMENTATION_PHASES.md`, then implement Phase 0 through Phase 7. Use Python FastAPI, HTML/CSS/JS frontend, Supabase PostgreSQL, and deploy to Vercel. Match all filter logic, pages, auth roles, and email scheduling described in the blueprint. Improve the UI per the design system. Seed with sample data for farm KF (Killara Feedlot).
