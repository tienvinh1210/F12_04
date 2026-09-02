# Deployment Guide — Vercel + Supabase

---

## Architecture options

### Option A: Split (recommended)
| Component | Host |
|-----------|------|
| Frontend (HTML/JS/CSS) | Vercel static |
| Python FastAPI API | Render, Fly.io, or Railway |
| PostgreSQL + Storage | Supabase |
| Email cron | Render cron or Vercel cron hitting API |

Vercel `vercel.json` rewrites `/api/*` → external API URL.

### Option B: Vercel serverless Python
- FastAPI as Vercel serverless functions (`api/index.py`)
- Cold starts may be slow for heavy chart generation
- 10s timeout on hobby tier — may need Pro for reports

### Option C: All-in Supabase
- Edge Functions for API
- More refactor required — not recommended for Phase 1

**Blueprint default: Option A**

---

## Supabase setup

### 1. Create project
- Region: closest to Australia (e.g. Sydney if available, else Singapore)
- Note `SUPABASE_URL` and keys

### 2. Run schema
Paste `database/001_schema.sql` in SQL Editor.

### 3. Create storage buckets
| Bucket | Public | Purpose |
|--------|--------|---------|
| logos | yes | Farm header logos |
| uploads | no | CSV archives |
| reports | no | Generated PDFs |

### 4. Storage policies (logos — public read)
```sql
CREATE POLICY "Public logo read" ON storage.objects
  FOR SELECT USING (bucket_id = 'logos');
```

### 5. Seed data
- Run Python seed script: users with real scrypt hashes
- Import sample CSV for farm KF

### 6. Connection string
Backend uses:
```
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```
Use **connection pooler** (port 6543) for serverless.

---

## Backend deploy (Render example)

### `render.yaml`
```yaml
services:
  - type: web
    name: livestock-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: JWT_SECRET
        generateValue: true
      - key: RESEND_API_KEY
        sync: false
      - key: CORS_ORIGINS
        value: https://your-app.vercel.app

  - type: cron
    name: email-scheduler
    schedule: "*/15 * * * *"
    buildCommand: pip install -r requirements.txt
    startCommand: python -m app.jobs.process_emails
```

---

## Frontend deploy (Vercel)

### Project structure for Vercel
```
frontend/          ← Root Directory in Vercel settings
  index.html
  login.html
  dashboard.html
  css/
  js/
  vercel.json
```

### `vercel.json`
```json
{
  "rewrites": [
    { "source": "/api/(.*)", "destination": "https://livestock-api.onrender.com/api/$1" },
    { "source": "/(.*)", "destination": "/$1" }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" }
      ]
    }
  ]
}
```

### Environment variables (Vercel — frontend)
```bash
# Only if frontend calls Supabase directly (optional)
VITE_API_URL=https://livestock-api.onrender.com
```

Frontend `api.js`:
```javascript
const API_BASE = window.API_URL || '/api';
```

### Deploy
```bash
cd frontend
vercel --prod
```

---

## Domain setup

1. Add custom domain in Vercel: `dashboard.yourfarm.com`
2. Update `CORS_ORIGINS` on API
3. Configure Resend domain DNS (SPF, DKIM) for email

### Multi-farm routing (optional)
- `killara.yourfarm.com` → same Vercel project, pass `?farm=KF` via middleware
- Vercel Edge Middleware reads subdomain → sets `farm_id` cookie

---

## Environment files

### `.env.example` (backend)
```bash
DATABASE_URL=postgresql://...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
JWT_SECRET=change-me-to-random-64-chars
JWT_EXPIRY_HOURS=24
RESEND_API_KEY=re_...
EMAIL_FROM=reports@yourdomain.com
EMAIL_DRY_RUN=false
CORS_ORIGINS=http://localhost:3000,https://your-app.vercel.app
CRON_SECRET=random-cron-secret
DEFAULT_TIMEZONE=Australia/Sydney
```

### Local development
```bash
# Terminal 1: API
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend (simple server)
cd frontend && python -m http.server 3000

# Or use Vite/live-server for hot reload
```

Frontend dev: set `API_BASE = 'http://localhost:8000/api'`

---

## CI/CD

### GitHub Actions (`.github/workflows/ci.yml`)
```yaml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r backend/requirements.txt
      - run: pytest backend/tests/
```

Vercel auto-deploys on push to `main`.

---

## Production checklist

- [ ] Supabase schema applied to prod project
- [ ] Default passwords changed
- [ ] `JWT_SECRET` and `CRON_SECRET` are strong random values
- [ ] `EMAIL_DRY_RUN=false`
- [ ] Resend domain verified
- [ ] CORS locked to production domain
- [ ] RLS enabled on `animal_data`
- [ ] Service role key only on backend
- [ ] HTTPS enforced
- [ ] Error monitoring (Sentry optional)
- [ ] Database backups enabled in Supabase (daily)

---

## Cost estimate (low traffic)

| Service | Tier | ~Cost |
|---------|------|-------|
| Supabase | Free | $0 |
| Vercel | Hobby | $0 |
| Render API | Free | $0 (sleeps) |
| Resend | Free | 3k emails/mo |

Upgrade Render to $7/mo for always-on API if needed.

---

## Rollback

1. **Code:** Vercel instant rollback to previous deployment
2. **Data:** Restore from `animal_data_snapshots` via admin API
3. **Schema:** Supabase point-in-time recovery (Pro plan)

---

## Monitoring

- API health: uptime monitor on `GET /api/health`
- Email cron: alert if `process_due_emails` returns `failed > 0`
- Supabase dashboard: query performance, storage usage
