# Admin Operations

Replaces the original Windows `admin_panel.bat` + R scripts in `admin_scripts/`.

---

## Original admin menu → New implementation

| # | Original | New |
|---|----------|-----|
| 1 | Update Farm Databases | `POST /api/admin/farms/{id}/upload` or `python admin.py upload` |
| 2 | Deploy Code Changes | `git push` → Vercel auto-deploy |
| 3 | Revert Farm from Backup | `POST /api/admin/farms/{id}/snapshots/{id}/restore` |
| 4 | View Farm Status | `GET /api/admin/farms/{id}/status` |
| 5 | View All Backups | `GET /api/admin/farms/{id}/snapshots` |
| 6 | Manage User Credentials | Admin UI or `python admin.py users` |

---

## CSV upload pipeline

### Step 1: Receive file
- Multipart upload or CLI reads from `data_upload/` folder
- Validate filename: `{farm_id}_*.csv`
- Validate `farm_id` exists in `farms` table

### Step 2: Pre-upload backup (snapshot)
```python
async def create_snapshot(farm_id: str, created_by: str):
    # Option A: COPY animal_data to animal_data_snapshots as JSON in Storage
    # Option B: pg_dump farm partition
    # Store record_count, snapshot_name = f"{farm_id}_backup_{date}"
```

Original naming: `FarmA_backup_20250122.duckdb`  
New naming: `KF_backup_20250122` in `animal_data_snapshots`

### Step 3: Parse CSV
```python
import pandas as pd

df = pd.read_csv(file)
df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

# Map known headers
COLUMN_MAP = {
    "eid": "eid", "date": "date", "breed": "breed",
    "treatment": "treatment", "mob": "mob", "sex": "sex",
    "finalpweight": "finalpweight", ...
}

df["date"] = pd.to_datetime(df["date"], dayfirst=True)  # DD/MM/YYYY
df["farm_id"] = farm_id
```

### Step 4: Validate
- Required: `eid`, `date`
- Reject if zero valid rows
- Log warnings for unmapped columns

### Step 5: Upsert with duplicate handling
```sql
INSERT INTO animal_data (farm_id, eid, date, ...)
VALUES (...)
ON CONFLICT (farm_id, eid, date)
DO UPDATE SET ...           -- if mode=overwrite
-- or DO NOTHING           -- if mode=skip
```

### Step 6: Archive file
Upload to Supabase Storage: `uploads/{farm_id}/archive/{filename}`

### Step 7: Log upload
Insert into `data_uploads` table.

---

## Farm status response

```json
{
  "farm_id": "KF",
  "farm_name": "Killara Feedlot",
  "record_count": 12118,
  "database_size_estimate": "12 MB",
  "last_modified": "2025-01-22T14:30:00Z",
  "snapshots_count": 5,
  "most_recent_snapshot": "KF_backup_20250122",
  "deployment_url": "https://livestock-dashboard.vercel.app/dashboard?farm=KF",
  "pending_uploads": []
}
```

---

## Snapshot restore

1. Confirm with user (safety snapshot of current state first)
2. Delete current `animal_data` rows for `farm_id`
3. Restore from snapshot storage
4. Log restore event

Original safety backup: `{farm}_before_revert_YYYYMMDD_HHMMSS`

---

## Logo management

### Storage structure
```
logos/
  KF/
    01_university.png
    02_sponsor.png
```

### Rules
- Formats: PNG, JPG, JPEG, SVG
- Recommended height: 50–60px (CSS scales width auto)
- Max ~100KB per file
- Display order: alphabetical by filename (use `01_`, `02_` prefixes)

### Upload
`POST /api/admin/farms/{farm_id}/logos` — multipart image

### Delete
`DELETE /api/admin/farms/{farm_id}/logos/{filename}`

Dashboard fetches `GET /api/farms/{farm_id}/logos` on load.

---

## User credential management

### View all users
```
ID:1  admin [ADMIN]
ID:2  owner [ADMIN]
ID:3  user
```

### Change username
- Validate unique
- `PUT /api/auth/username`

### Change password
- Hash with scrypt before store
- `PUT /api/auth/password`

---

## Python CLI (`admin-cli/admin.py`)

Optional but recommended for operators who used `.bat` files:

```bash
# Check setup
python admin.py check

# Upload CSV
python admin.py upload --farm KF --file data_upload/KF_2025-01-22.csv --mode skip

# View farm status
python admin.py status --farm KF

# List snapshots
python admin.py snapshots --farm KF

# Restore snapshot
python admin.py restore --farm KF --snapshot 42

# Manage users
python admin.py users list
python admin.py users password --id 1 --password newpass
```

Uses same API with admin service token or direct DB connection.

---

## Adding a new farm

1. Insert into `farms` table:
   ```sql
   INSERT INTO farms (farm_id, farm_name, slug)
   VALUES ('FarmB', 'Smith Ranch', 'smith-ranch');
   ```
2. Grant user access in `user_farm_access`
3. Upload initial CSV: `FarmB_2025-01-22.csv`
4. Upload logos to Storage
5. Dashboard available at `?farm=FarmB`

No per-farm deployment needed (unlike shinyapps.io).

---

## Multi-farm deployment note

Original: new farms deployed **sequentially** to shinyapps.io to prevent data mixing.

New: single app, `farm_id` column isolation + RLS. No sequential deploy required.

---

## Directory mapping (old → new)

| Old path | New location |
|----------|--------------|
| `farms.csv` | `farms` table |
| `farm_databases/{id}_data.duckdb` | `animal_data` WHERE farm_id = id |
| `farm_backups/{id}/` | `animal_data_snapshots` + Storage |
| `farm_logos/{id}/` | Storage `logos/{id}/` |
| `data_upload/` | CLI watches folder OR web upload |
| `data_upload/archive/` | Storage `uploads/{id}/archive/` |
| `src/credentials.duckdb` | `users` table |
