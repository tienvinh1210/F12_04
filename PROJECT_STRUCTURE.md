# Project Structure

Correct layout for the Livestock Dashboard. **Do not move these folders** unless you update all references in `docker-compose.yml`, docs, and scripts.

```
COMP3888/                          ← project root (open this folder in your IDE)
│
├── api/                           ← Vercel serverless entry (deploy only)
│   ├── index.py                   # Imports backend/app/main.py
│   └── requirements.txt           # Points to backend/requirements.txt
│
├── backend/                       ← Python FastAPI application
│   ├── .env                       ← YOUR SECRETS (create from .env.example)
│   ├── .env.example
│   ├── requirements.txt
│   └── app/
│       ├── main.py                # FastAPI app + router registration
│       ├── config.py
│       ├── db.py
│       ├── auth/
│       ├── models/
│       ├── routers/
│       ├── services/
│       └── utils/
│   └── tests/
│
├── frontend/                      ← Static HTML/CSS/JS (served by Vercel or python -m http.server)
│   ├── index.html                 # Redirects to login
│   ├── login.html
│   ├── dashboard.html
│   ├── css/
│   ├── js/
│   │   └── pages/                 # One JS file per dashboard tab
│   └── assets/
│       └── logos/                 # Farm header logos (KF/, default.svg)
│
├── database/                      ← SQL schema (ROOT level — not inside backend/)
│   └── 001_schema.sql             # Run in Supabase SQL Editor
│
├── scripts/
│   └── seed.py                    # Seed users + KF sample data
│
├── admin-cli/
│   └── admin.py                   # Optional CSV upload CLI
│
├── .env.example                   # Reference only — copy to backend/.env
├── docker-compose.yml             # Local Postgres (expects ./database/ at root)
├── vercel.json                    # Vercel routes + cron
│
└── *.md                           # Blueprint & documentation
```

---

## Common mistakes

### 1. `database/` moved inside `backend/`

**Wrong:**
```
backend/database/001_schema.sql
```

**Correct:**
```
database/001_schema.sql
```

`docker-compose.yml`, `SUPABASE_SETUP.md`, and `README.md` all expect the schema at the **project root**.

---

### 2. Running commands from the wrong directory

| Task | Run from | Command |
|------|----------|---------|
| Start API | `backend/` | `uvicorn app.main:app --reload --port 8000` |
| Serve frontend | `frontend/` | `python -m http.server 3000` |
| Seed database | **project root** | `python scripts/seed.py` |
| Run tests | `backend/` | `PYTHONPATH=. pytest tests/ -v` |
| Docker Postgres | **project root** | `docker compose up -d` |

---

### 3. Putting `.env` in the wrong place

**Wrong:** `COMP3888/.env` only (unless you symlink)

**Correct:** `backend/.env` — the FastAPI app loads env from here when you run uvicorn from `backend/`.

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your Supabase DATABASE_URL, JWT_SECRET, etc.
```

The root `.env.example` is a convenience copy; the app reads `backend/.env`.

---

### 4. Serving frontend from `backend/`

The frontend is a **separate folder**. Do not put `login.html` inside `backend/`.

- Local: `cd frontend && python -m http.server 3000`
- Production: Vercel serves `frontend/` as static files (see `vercel.json`)

---

### 5. Confusing `api/` and `backend/`

| Folder | Purpose |
|--------|---------|
| `backend/app/` | All application code — use this for local dev |
| `api/index.py` | Thin Vercel wrapper that imports `backend/app/main.py` |

You develop in `backend/`; Vercel deploys both `api/` and `frontend/`.

---

## What each top-level folder is for

| Path | Keep at root? | Notes |
|------|---------------|-------|
| `backend/` | Yes | Python API |
| `frontend/` | Yes | Dashboard UI |
| `database/` | Yes | SQL migrations/schema |
| `scripts/` | Yes | One-off scripts (seed) |
| `api/` | Yes | Vercel only |
| `admin-cli/` | Yes | Optional admin tools |
| `.venv/` | Yes (gitignored) | Python virtualenv — create at project root |

---

## Quick health check

From project root, after fixing structure:

```bash
# 1. Schema exists at root
test -f database/001_schema.sql && echo "OK: schema at root"

# 2. Backend app imports
cd backend && PYTHONPATH=. python -c "from app.main import app; print('OK: FastAPI app')"

# 3. Frontend entry points exist
test -f frontend/login.html && test -f frontend/dashboard.html && echo "OK: frontend"
```

---

## Related docs

- [README.md](README.md) — quick start
- [SUPABASE_SETUP.md](SUPABASE_SETUP.md) — database setup
- [00_BLUEPRINT_MASTER.md](00_BLUEPRINT_MASTER.md) — original architecture spec
