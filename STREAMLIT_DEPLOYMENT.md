# Streamlit Deployment Guide

Host the Livestock Dashboard on **[Streamlit Community Cloud](https://share.streamlit.io)** (free), using the same Supabase database as the FastAPI app.

> **Important:** Streamlit is a different UI framework from the HTML/Vercel app.  
> `streamlit_app.py` reuses the same Python filter/chart/auth logic against Supabase — it is not the Vercel frontend.

---

## Why Streamlit instead of Vercel?

| | Vercel | Streamlit Cloud |
|--|--------|-----------------|
| Stack | Static HTML + Python serverless | Python Streamlit UI |
| Login issues | Cold starts / env / timeouts can break `/api/auth/login` | Runs as one Python process |
| Free tier | Hobby limits on Python | Generous for student/demo apps |
| Best for | Production web apps | Fast demos, clients, coursework |

---

## Prerequisites

1. Supabase project ready (schema + seeded `Data.csv`) — see [SUPABASE_SETUP.md](SUPABASE_SETUP.md)
2. Code pushed to GitHub (e.g. `tdan0407/F12_04_Python`)
3. Free account at [share.streamlit.io](https://share.streamlit.io) (sign in with GitHub)

---

## Step 1 — Test locally

```bash
cd /path/to/COMP3888
source .venv/bin/activate
pip install -r requirements-streamlit.txt

# Create secrets from your working backend/.env DATABASE_URL
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml — paste your Supabase pooler URL
# Remember: encode @ in password as %40

streamlit run streamlit_app.py
```

Open **http://localhost:8501** and log in with `admin` / `admin123`.

---

## Step 2 — Deploy on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
2. Fill in:

| Field | Value |
|-------|--------|
| **Repository** | `your-user/F12_04_Python` (or your repo name) |
| **Branch** | `main` |
| **Main file path** | `streamlit_app.py` |
| **App URL** (optional) | e.g. `livestock-dashboard` |

3. Click **Advanced settings** → **Secrets** and paste:

```toml
DATABASE_URL = "postgresql://postgres.YOUR_REF:YOUR_PASSWORD@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"
```

Use the **same** `DATABASE_URL` that works in `backend/.env` (pooler port **6543**, password URL-encoded).

4. Click **Deploy**

Wait 1–3 minutes for the build. Your app URL will look like:

```
https://livestock-dashboard.streamlit.app
```

---

## Step 3 — Login

| Username | Password |
|----------|----------|
| `admin` | `admin123` |
| `owner` | `owner123` |
| `user` | `user123` |

Change these passwords before sharing with real clients.

---

## What the Streamlit app includes

| Feature | Status |
|---------|--------|
| Login (scrypt + Supabase `users` table) | ✓ |
| Farm selector | ✓ |
| Sidebar filters (year/month/day/sex/treatment/breed/mob/EID/measure) | ✓ |
| Summary KPI cards | ✓ |
| Time Series (Plotly) | ✓ |
| Distributions | ✓ |
| Cohorts | ✓ |
| Data table + CSV download | ✓ |
| Customise chart | ✓ |
| Email scheduling / admin CSV upload | ✗ (use FastAPI/admin CLI for that) |
| Saved views | ✗ (Streamlit session only) |

---

## Project files

| File | Purpose |
|------|---------|
| `streamlit_app.py` | Main Streamlit UI |
| `requirements-streamlit.txt` | Dependencies for Streamlit Cloud |
| `.streamlit/config.toml` | Theme / server settings |
| `.streamlit/secrets.toml.example` | Template for secrets |
| `backend/app/` | Shared business logic (filters, charts, auth) |

Streamlit Cloud installs from `requirements-streamlit.txt` **or** a root `requirements.txt`.  
If the cloud builder looks for `requirements.txt` by default, either:

- Keep `requirements-streamlit.txt` and set it in app settings if available, **or**
- Copy / symlink:

```bash
cp requirements-streamlit.txt requirements.txt
```

(Recommended for Streamlit Cloud — it auto-detects root `requirements.txt`.)

---

## Secrets checklist

On Streamlit Cloud → **Manage app → Settings → Secrets**:

```toml
DATABASE_URL = "postgresql://postgres.[REF]:[PASS]%40[rest]@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"
```

| Rule | Why |
|------|-----|
| Port `6543` | Connection pooler (required for cloud) |
| Encode `@` in password as `%40` | Otherwise URL parses wrong |
| Never commit `.streamlit/secrets.toml` | Already in `.gitignore` |

---

## Updating the app

```bash
git add streamlit_app.py requirements-streamlit.txt requirements.txt .streamlit/
git commit -m "Add Streamlit dashboard"
git push
```

Streamlit Cloud auto-redeploys on push to the linked branch.  
Or click **Reboot** / **Rerun** in the app menu.

---

## Troubleshooting

### App fails to start / red error screen

- Open **Manage app → Logs**
- Common: missing `DATABASE_URL` in Secrets
- Common: wrong password encoding (`@` → `%40`)

### Login always fails

- Confirm seed ran: users `admin` / `owner` / `user` exist in Supabase
- Test URL locally with the same `DATABASE_URL` in `.streamlit/secrets.toml`

### `ModuleNotFoundError: app`

- Main file must be **`streamlit_app.py` at repo root** (it adds `backend/` to `sys.path`)
- Do not set Main file to `backend/...`

### Slow first load

- Normal cold start on free tier; first query loads all farm rows into pandas
- Subsequent filter changes are faster within the session

### “Too many connections”

- Use pooler port **6543**, not direct `5432`
- Reboot the Streamlit app to drop stale connections

---

## Local commands (quick reference)

```bash
# Install
pip install -r requirements-streamlit.txt

# Secrets
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit DATABASE_URL

# Run
streamlit run streamlit_app.py
```

---

## Related docs

- [SUPABASE_SETUP.md](SUPABASE_SETUP.md) — database
- [VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md) — original Vercel path (optional)
- [README.md](README.md) — FastAPI local development
