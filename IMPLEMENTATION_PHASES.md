# Implementation Phases

Build in this order. Each phase has deliverables and acceptance checks. Do not skip phases.

---

## Phase 0 — Scaffold & infrastructure (Day 1)

### Tasks
1. Create repo with `backend/` and `frontend/` structure from `00_BLUEPRINT_MASTER.md`
2. Create Supabase project; run `database/001_schema.sql`
3. Configure `.env` from `.env.example`
4. FastAPI hello-world at `GET /api/health`
5. Serve `frontend/login.html` statically on Vercel

### Deliverables
- [ ] `GET /api/health` returns `{"status":"ok"}`
- [ ] Supabase tables exist
- [ ] Vercel project linked (can be preview deploy)

---

## Phase 1 — Auth & data seed (Day 1–2)

### Tasks
1. Implement `POST /api/auth/login` with scrypt password verification
2. Seed 3 default users (admin, owner, user) — see schema SQL
3. Implement JWT session cookie or `Authorization: Bearer` token
4. `GET /api/auth/me` returns user + `is_admin`
5. Import sample CSV for farm `KF` (~12k rows) into `animal_data`
   - Source column mapping in `DATA_MODEL.md`
6. Login page: form → token → redirect to dashboard

### Deliverables
- [ ] Login works with default credentials
- [ ] Non-admin cannot call EID filter endpoint
- [ ] `animal_data` has records for `KF`

### Acceptance
```bash
curl -X POST /api/auth/login -d '{"username":"admin","password":"admin123"}'
# → 200 + token

curl /api/filters/choices?farm_id=KF -H "Authorization: Bearer ..."
# → years, breeds, mobs, etc.
```

---

## Phase 2 — Filter engine & API (Day 2–3)

### Tasks
1. Port `filter_data()` to `FilterService.apply_filters()`
2. Port `grouped_data` expand logic to `FilterService.build_grouped_data()`
3. Port label functions to `FilterService.create_group_labels()`
4. Endpoints:
   - `GET /api/filters/choices?farm_id=`
   - `POST /api/data/query` — body: filter state → `{ filtered, processed, grouped, record_count }`
5. EID anonymization in response layer for non-admin
6. Frontend: sidebar filter components + debounced query (300ms)
7. Record count display: "Showing X of Y records"
8. Clear all filters button
9. Saved Views (localStorage only) — save/load/delete filter presets

### Deliverables
- [ ] Filter results match R app for same inputs (spot-check 5 scenarios)
- [ ] Empty state shows when zero records
- [ ] Saved views persist across page reload

---

## Phase 3 — Dashboard pages 1–4 (Day 3–5)

### Page 1: Summary Stats
- `POST /api/summary/stats` with filters + measure
- KPI cards per `full_group`: Last Day, Last 15 Days, Last Month, Overall
- Each card: mean, min, max, median, count with units

### Page 2: Time Series
- `POST /api/charts/timeseries`
- Daily mean by group; Plotly line chart
- Controls: point size slider (1–5), show trend line checkbox (LOESS/smooth)

### Page 3: Distributions
- `POST /api/charts/distribution`
- Histogram (bins 10–50, default 20) + box plot
- Mean/median vertical lines on histogram
- Sample max 200 points/group for histogram if >3000 rows

### Page 4: Cohorts
- `POST /api/cohorts/analyze?percentile=10|15|20`
- Top/bottom cohort stats + animal list modal
- Mixed-filter warning if Overall + specific selected
- Cohort timeline chart for selected animals
- Export top/bottom CSV

### Deliverables
- [ ] All 4 pages render with shared filters
- [ ] Charts interactive (legend toggle)
- [ ] Info alerts match original copy (legend tip, cohort explanation)

---

## Phase 4 — Pages 5–7 (Day 5–7)

### Page 5: Data Management
- Paginated table (server-side pagination if >1000 rows)
- Column filters on table
- `GET /api/data/export.csv` with current filters

### Page 6: Customise
- Chart builder: type, title, X, Y, group, aggregation, trend line
- Client-side or server-side aggregation endpoint
- Live preview with Plotly

### Page 7: Reports
- Export chart PNG (timeseries, distribution, summary)
- Export report PDF/HTML with selected sections
- Email: Send Now + Schedule (daily/weekly/monthly)
- List/manage scheduled emails (activate, delete)

### Deliverables
- [ ] CSV download works
- [ ] PDF report generates with filter summary
- [ ] Email schedule stored in DB

---

## Phase 5 — Admin & multi-farm (Day 7–8)

### Tasks
1. `farms` CRUD (admin only)
2. CSV upload pipeline:
   - Validate `{farm_id}_YYYY-MM-DD.csv`
   - Backup snapshot before merge
   - SKIP vs OVERWRITE duplicates
3. Logo upload to Supabase Storage
4. `GET /api/farms/{id}/logos` for header bar
5. User management: change username/password
6. Optional: Python CLI `admin.py upload --farm KF --file data.csv`

### Deliverables
- [ ] New farm can be onboarded end-to-end
- [ ] Logos display in header sorted alphabetically

---

## Phase 6 — Email worker & polish (Day 8–9)

### Tasks
1. Background scheduler (Vercel Cron, Supabase pg_cron, or Render cron)
2. `process_due_emails()` — send reports with attachments
3. Timezone: `Australia/Sydney`
4. UI polish: loading states, mobile sidebar, toast notifications
5. Performance: DB indexes, query EXPLAIN on heavy endpoints

### Deliverables
- [ ] Scheduled email sends within 15 min of due time
- [ ] Lighthouse accessibility score ≥ 85

---

## Phase 7 — Testing & deployment (Day 9–10)

### Tasks
1. pytest: filter logic, cohort math, anonymization, report generation
2. Playwright or manual test script for critical flows
3. Production Vercel deploy + Supabase prod project
4. Change default passwords
5. Document runbook in project README

### Deliverables
- [ ] All tests pass in CI
- [ ] Production URL live
- [ ] `TESTING.md` checklist complete

---

## Estimated timeline

| Phase | Duration |
|-------|----------|
| 0 | 4 hours |
| 1 | 8 hours |
| 2 | 12 hours |
| 3 | 16 hours |
| 4 | 16 hours |
| 5 | 8 hours |
| 6 | 8 hours |
| 7 | 8 hours |
| **Total** | **~80 hours** (2 dev-weeks) |

---

## Parallelization hint (for AI agents)

These can run in parallel after Phase 2:
- Frontend page JS (one file per page)
- Backend service modules (summary, cohort, distribution)
- Admin CLI
- Email worker

Sync point: Phase 2 filter API must be stable before page work begins.
