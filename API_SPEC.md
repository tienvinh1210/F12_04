# API Specification

Base URL: `/api`  
Auth: `Authorization: Bearer <jwt>` on all routes except `/auth/login` and `/health`  
Content-Type: `application/json` unless noted  
Timezone: `Australia/Sydney` for all date/time operations

---

## Health

### `GET /health`
**Auth:** none

**Response 200:**
```json
{"status": "ok", "version": "1.0.0"}
```

---

## Authentication

### `POST /auth/login`
**Auth:** none

**Body:**
```json
{"username": "admin", "password": "admin123"}
```

**Response 200:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": 1,
    "username": "admin",
    "is_admin": true,
    "farms": [{"farm_id": "KF", "farm_name": "Killara Feedlot", "slug": "killara-feedlot"}]
  }
}
```

**Response 401:** `{"detail": "Invalid credentials"}`

### `GET /auth/me`
**Response 200:** same `user` object as login

### `POST /auth/logout`
**Response 200:** `{"detail": "logged out"}`  
(Client should delete token; optional server-side blocklist)

### `PUT /auth/password` (admin or self)
**Body:** `{"user_id": 3, "new_password": "..."}`

### `PUT /auth/username` (admin)
**Body:** `{"user_id": 3, "new_username": "john_smith"}`

---

## Farms

### `GET /farms`
List farms current user can access.

### `GET /farms/{farm_id}`
Farm details + logo URLs.

### `GET /farms/{farm_id}/logos`
**Response:**
```json
{
  "logos": [
    {"filename": "01_university.png", "url": "https://...supabase.co/storage/..."}
  ]
}
```
Sorted alphabetically by filename.

---

## Filters

### `GET /filters/choices?farm_id=KF`
Returns all dropdown choices. See `DATA_MODEL.md` for shape.  
Omit `eids` if not admin.

---

## Data query (core)

### `POST /data/query`
**Body:** filter state (see `DATA_MODEL.md`)

**Response 200:**
```json
{
  "record_count": 450,
  "total_records": 12118,
  "filtered": [...],           // paginated optional: ?page=1&page_size=100
  "processed": [...],          // with group + treatment_display
  "grouped": [...],            // expanded group comparison rows
  "common_filters_note": "Comparing groups by Sex only"
}
```

**Performance:** For large responses, support:
- `include_rows: false` — stats only
- `page` + `page_size` on `filtered`

### `GET /data/export.csv?farm_id=KF&...`
Query params mirror filter state.  
Returns `text/csv` attachment.  
EIDs anonymized for non-admin.

---

## Summary

### `POST /summary/stats`
**Body:** filter state + `measure`

**Response:**
```json
{
  "groups": [
    {
      "full_group": "Sex: Steer, Treatment: Drench, Breed: Brahman X, Mob: Front, EID: *****",
      "windows": {
        "last_day": {"mean": 620.5, "min": 500, "max": 700, "median": 615, "count": 42, "label": "Last Day (14/10/2023)"},
        "last_15_days": {...},
        "last_month": {...},
        "overall": {...}
      }
    }
  ]
}
```

---

## Charts

### `POST /charts/timeseries`
**Body:** filter state + `measure` + optional `point_size`, `show_smooth`

**Response:**
```json
{
  "series": [
    {"date": "2023-10-14", "group": "Overall Average", "value": 612.5, "count": 42}
  ],
  "y_label": "finalpweight (kg)"
}
```

### `POST /charts/distribution`
**Body:** filter state + `measure` + `hist_bins` (10-50)

**Response:**
```json
{
  "histogram": {
    "bins": [...],
    "groups": [{"group": "...", "values": [...]}],
    "mean": 600.0,
    "median": 580.0
  },
  "boxplot": {
    "groups": [{"group": "...", "min": 400, "q1": 500, "median": 550, "q3": 650, "max": 700}]
  }
}
```

Server applies sampling caps per `MIGRATION_FROM_R.md`.

---

## Cohorts

### `POST /cohorts/analyze`
**Body:** filter state + `measure` + `percentile` (10|15|20)

**Response:** see `DATA_MODEL.md` cohort shape.

### `GET /cohorts/export.csv?cohort=top|bottom&...`
Export animal list for cohort.

---

## Customise

### `POST /charts/custom`
**Body:**
```json
{
  "farm_id": "KF",
  "filters": {...},
  "chart_type": "line",
  "title": "Custom Chart",
  "x_col": "date",
  "y_col": "finalpweight",
  "group_col": "sex",
  "agg_fun": "mean",
  "smooth": false,
  "bar_position": "stack",
  "hist_bins": 20
}
```

**Response:** Plotly-compatible JSON `{"data": [...], "layout": {...}}`

---

## Reports

### `POST /reports/chart.png`
**Body:** `{"chart_source": "Time Series|Distribution|Summary", "filters": {...}}`  
**Response:** `image/png`

### `POST /reports/generate`
**Body:**
```json
{
  "farm_id": "KF",
  "filters": {...},
  "filename": "killara_report",
  "format": "PDF",
  "charts": ["Time Series", "Distribution", "Cohorts", "Summary Statistics"]
}
```
**Response:** file download or `{"download_url": "..."}`

---

## Email schedules

### `GET /email/schedules?farm_id=KF`
List schedules for farm.

### `POST /email/schedules`
**Body:**
```json
{
  "farm_id": "KF",
  "recipient_email": "manager@farm.com",
  "schedule_name": "Weekly Summary",
  "frequency": "weekly",
  "send_time": "09:00",
  "day_of_week": 1,
  "email_subject": "Weekly Livestock Report",
  "email_body": "Please find attached...",
  "report_filters": {...},
  "report_charts": ["Distribution", "Summary Statistics"],
  "report_format": "PDF"
}
```

### `POST /email/send-now`
**Body:** same as schedule but no frequency — sends immediately.

### `PATCH /email/schedules/{id}`
**Body:** `{"is_active": false}`

### `DELETE /email/schedules/{id}`

### `POST /email/process-due` (cron only)
**Auth:** `X-Cron-Secret` header  
Processes all due schedules. Returns `{"sent": 3, "failed": 0}`.

---

## Admin (requires admin role)

### `POST /admin/farms`
Create farm: `{"farm_id": "FarmB", "farm_name": "...", "slug": "..."}`

### `POST /admin/farms/{farm_id}/upload`
**Content-Type:** `multipart/form-data`  
Fields: `file` (CSV), `duplicate_mode` (`skip`|`overwrite`)

**Response:**
```json
{
  "rows_inserted": 150,
  "rows_skipped": 10,
  "rows_overwritten": 0,
  "snapshot_id": 42
}
```

### `POST /admin/farms/{farm_id}/snapshots/{snapshot_id}/restore`

### `GET /admin/farms/{farm_id}/status`
```json
{
  "record_count": 12118,
  "last_upload": "2025-01-22T10:00:00Z",
  "snapshots_count": 5,
  "pending_uploads": []
}
```

### `POST /admin/farms/{farm_id}/logos`
Upload logo image (PNG/JPG/SVG, max 100KB recommended).

### `GET /admin/users`
### `POST /admin/users`
### `PUT /admin/users/{id}`

---

## Error format

```json
{
  "detail": "Human readable message",
  "code": "VALIDATION_ERROR",
  "fields": {"year": "required"}
}
```

| Status | When |
|--------|------|
| 400 | Invalid filter state, bad CSV |
| 401 | Missing/invalid token |
| 403 | Non-admin accessing admin route |
| 404 | Farm not found or no access |
| 422 | Pydantic validation |
| 500 | Server error |

---

## Python FastAPI router registration example

```python
from fastapi import FastAPI
from app.routers import auth, animals, filters, reports, admin, email_schedules

app = FastAPI(title="Livestock Dashboard API")
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(filters.router, prefix="/api/filters", tags=["filters"])
app.include_router(animals.router, prefix="/api/data", tags=["data"])
# ... etc
```

---

## Rate limiting (recommended)

- Login: 10 req/min per IP
- Data query: 60 req/min per user
- Export: 10 req/min per user
