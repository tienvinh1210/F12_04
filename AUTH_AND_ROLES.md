# Authentication & Roles

## Overview

The original app used **shinymanager** with passwords stored as **scrypt** hashes in a DuckDB `credentials` table. The rebuild uses a custom `users` table in Supabase with the same hashing approach for migration compatibility.

**Do not use Supabase Auth** unless you want to migrate users — the blueprint assumes custom JWT auth for parity with the original 3-account model.

---

## User accounts

| ID | Username | Default password | is_admin | Purpose |
|----|----------|------------------|----------|---------|
| 1 | admin | admin123 | true | Full management |
| 2 | owner | owner123 | true | Farm owner access |
| 3 | user | user123 | false | Privacy-restricted viewer |

**is_admin is fixed per account** (not editable). Only username and password change.

---

## Password hashing

### Original (R scrypt package)
```r
scrypt::hashPassword("admin123")
scrypt::verifyPassword(stored_hash, password)
```

### Python equivalent
```python
# Option A: passlib scrypt
from passlib.hash import scrypt
scrypt.hash("admin123")
scrypt.verify("admin123", stored_hash)

# Option B: hashlib scrypt (stdlib) — match R params if needed
import hashlib
hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
```

On first deploy, run a seed script that generates real hashes. The placeholder hashes in `001_schema.sql` must be replaced.

---

## JWT structure

```json
{
  "sub": "1",
  "username": "admin",
  "is_admin": true,
  "farm_ids": ["KF"],
  "exp": 1735689600,
  "iat": 1735603200
}
```

- Algorithm: HS256
- Secret: `JWT_SECRET` env var
- Expiry: 24 hours (configurable)
- Store in `sessionStorage` as `access_token` (not localStorage for security)

---

## Login flow

```
User → POST /api/auth/login
     → Verify scrypt hash
     → Check user.is_active
     → Load user_farm_access → farm list
     → Issue JWT
     → Frontend stores token
     → Redirect to dashboard
```

Every API request:
```
Authorization: Bearer <token>
→ decode JWT
→ load user (or trust claims)
→ attach to request.state.user
→ enforce farm_id access
```

---

## EID anonymization (critical privacy feature)

### Rule
If `user.is_admin == false`, replace every `eid` field in API responses with `"*****"`.

### Apply at
- `POST /api/data/query` — filtered, processed, grouped arrays
- `GET /api/data/export.csv`
- `POST /api/cohorts/analyze` — animals list
- All table/chart data endpoints

### Do NOT anonymize
- Filter choice endpoint can omit `eids` entirely for non-admin (preferred)
- Admin endpoints

### Implementation pattern (Python)
```python
def anonymize_records(records: list[dict], is_admin: bool) -> list[dict]:
    if is_admin:
        return records
    return [{**r, "eid": "*****"} if "eid" in r else r for r in records]
```

Apply in a single middleware/response wrapper to avoid missing a path.

---

## Authorization matrix

| Endpoint | admin | owner | user |
|----------|-------|-------|------|
| View dashboard pages | ✓ | ✓ | ✓ |
| EID filter | ✓ | ✓ | ✗ |
| See real EIDs | ✓ | ✓ | ✗ |
| Export CSV | ✓ | ✓ | ✓ (anon EIDs) |
| Schedule emails | ✓ | ✓ | ✓ |
| Admin upload CSV | ✓ | ✓* | ✗ |
| Manage users | ✓ | ✗ | ✗ |

*Owner admin upload is optional — restrict to `admin` only if simpler.

---

## Farm access control

Before any `farm_id` query:
```python
def assert_farm_access(user_id: int, farm_id: str, db):
    if not db.user_has_farm(user_id, farm_id):
        raise HTTPException(403, "No access to this farm")
```

---

## Logout

1. Frontend: clear `sessionStorage.access_token`
2. Redirect to `login.html`
3. Optional: POST `/api/auth/logout` for audit log

Custom logout button in navbar (not browser basic auth).

---

## Session invalidation

On password change for user X:
- Optionally invalidate all tokens for user X (token version in JWT claim)

---

## Security checklist

- [ ] HTTPS only in production
- [ ] `SUPABASE_SERVICE_ROLE_KEY` never in frontend
- [ ] JWT secret ≥ 32 random bytes
- [ ] Rate limit login endpoint
- [ ] Change default passwords before go-live
- [ ] CORS restricted to Vercel domain
- [ ] SQL injection prevented via parameterized queries (asyncpg/SQLAlchemy)
- [ ] CSV upload size limit (e.g. 50MB)
- [ ] Cron endpoint protected by `X-Cron-Secret`

---

## Optional: Supabase Auth migration path

If later migrating to Supabase Auth:
1. Map `users.id` → `auth.users.id`
2. Use RLS policies on `animal_data` with `auth.uid()`
3. Store `is_admin` in `raw_user_meta_data`
4. Keep EID anonymization in Edge Function or view

Not required for initial build.
