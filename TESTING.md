# Testing & Acceptance Criteria

---

## Test pyramid

```
        ┌─────────────┐
        │  E2E (few)  │  Playwright / manual checklist
        ├─────────────┤
        │ Integration │  API tests with test DB
        ├─────────────┤
        │ Unit (many) │  filter, cohort, kpi, labels
        └─────────────┘
```

---

## Unit tests (pytest)

Location: `backend/tests/`

### `test_filter_service.py`
- [ ] `filter_data` year required raises
- [ ] month "All" skips month filter
- [ ] day filter works
- [ ] sex "Overall" includes all
- [ ] treatment "No Treatment" matches NULL
- [ ] eid filter ignored when `is_admin=False`
- [ ] empty result when no match

### `test_group_labels.py`
- [ ] single group all Overall → "Overall Average"
- [ ] varying sex only → "Sex: Steer | ..."
- [ ] NA treatment → "No Treatment"
- [ ] full_group includes all dimensions

### `test_grouped_data.py`
- [ ] Overall + specific sex expands correctly
- [ ] non-admin eid always Overall
- [ ] product of filter values produces correct row count

### `test_summary_service.py`
- [ ] `subset_by_window(1)` returns only max date
- [ ] `subset_by_window(15)` correct range
- [ ] `kpi_block` handles empty df
- [ ] currency formatting for animalvalue

### `test_cohort_service.py`
- [ ] 10% of 100 animals = 10 top, 10 bottom
- [ ] ranking by mean measure descending
- [ ] mixed warning when Overall + specific

### `test_anonymization.py`
- [ ] non-admin gets `*****` for eid
- [ ] admin gets real eid
- [ ] nested dicts anonymized

### `test_auth.py`
- [ ] valid login returns token
- [ ] invalid password 401
- [ ] scrypt verify works

### `test_report_generator.py`
- [ ] PDF generates non-empty file
- [ ] filter summary includes year
- [ ] chart PNG created for distribution

### `test_email_service.py`
- [ ] `compute_next_send` daily rolls to tomorrow if past
- [ ] weekly respects day_of_week
- [ ] dry run does not call Resend

---

## API integration tests

Use `httpx.AsyncClient` + test database (Supabase branch or local Postgres).

```python
@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c

async def test_login_and_query(client):
    r = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = r.json()["access_token"]
    r = await client.post("/api/data/query", json={...}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["record_count"] > 0
```

### Endpoints to integration test
- [ ] POST /auth/login
- [ ] GET /filters/choices
- [ ] POST /data/query
- [ ] POST /summary/stats
- [ ] POST /charts/timeseries
- [ ] POST /charts/distribution
- [ ] POST /cohorts/analyze
- [ ] GET /data/export.csv
- [ ] POST /admin/farms/KF/upload (admin token)
- [ ] POST /email/schedules

---

## Frontend manual checklist

### Login
- [ ] Valid credentials → dashboard
- [ ] Invalid credentials → error message
- [ ] Enter key submits form

### Filters (all pages)
- [ ] Year change updates all pages
- [ ] Clear all filters resets defaults
- [ ] Record count updates
- [ ] Saved view save/load/delete works
- [ ] EID filter hidden for user role

### Summary Stats
- [ ] KPI cards show per group
- [ ] Units display correctly ($, kg)
- [ ] Empty state when no data

### Time Series
- [ ] Chart renders with multiple groups
- [ ] Legend toggle works
- [ ] Trend line toggle works
- [ ] Point size slider works

### Distributions
- [ ] Histogram + box plot side by side
- [ ] Bin slider updates histogram

### Cohorts
- [ ] Top/bottom stats correct
- [ ] View animals modal works
- [ ] Export CSV works
- [ ] Mixed warning shows when appropriate
- [ ] Percentile selector works

### Data Management
- [ ] Table paginates
- [ ] CSV download works
- [ ] EIDs anonymized for user

### Customise
- [ ] All chart types render
- [ ] Axis selection works
- [ ] Aggregation changes chart

### Reports
- [ ] Chart PNG downloads
- [ ] PDF report downloads
- [ ] Send now email works (or dry run logs)
- [ ] Schedule appears in table

### Admin
- [ ] CSV upload inserts rows
- [ ] Duplicate skip mode works
- [ ] Logos appear in header

### Responsive
- [ ] Mobile sidebar drawer works
- [ ] Charts resize on narrow screen

---

## Performance benchmarks

| Operation | Target |
|-----------|--------|
| POST /data/query (12k rows, filtered) | < 500ms |
| Time series chart render | < 1s |
| Distribution with sampling | < 1s |
| CSV export 10k rows | < 3s |
| PDF report generation | < 10s |

---

## Security tests

- [ ] Non-admin cannot access `/api/admin/*`
- [ ] User cannot access other farm's data
- [ ] JWT expired → 401 → redirect login
- [ ] SQL injection in filter values blocked
- [ ] CSV upload rejects non-CSV files
- [ ] Cron endpoint rejects without secret

---

## CI configuration

```yaml
# .github/workflows/ci.yml
- run: pytest backend/tests/ -v --cov=app --cov-report=term-missing
- run: ruff check backend/
```

Minimum coverage target: **80%** on `services/` directory.

---

## Definition of done

Project is complete when:

1. All unit tests pass
2. All API integration tests pass
3. Manual checklist 100% checked
4. Deployed to production Vercel URL
5. Sample farm KF loads with real data
6. At least one scheduled email sent successfully in staging
7. Default passwords changed in production
8. README documents local setup in < 10 steps

---

## Sample pytest for filter parity

```python
import pandas as pd
from app.services.filter_service import filter_data, FilterState

def test_treatment_no_treatment():
    df = pd.DataFrame({
        "date": pd.to_datetime(["2023-10-01", "2023-10-01"]),
        "treatment": [None, "Drench"],
        "sex": ["Steer", "Steer"],
        "breed": ["A", "A"],
        "mob": ["F", "F"],
        "eid": ["1", "2"],
    })
    filters = FilterState(year=2023, treatment=["No Treatment"])
    result = filter_data(df, filters, is_admin=True)
    assert len(result) == 1
    assert pd.isna(result.iloc[0]["treatment"])
```
