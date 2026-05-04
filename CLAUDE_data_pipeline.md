# Croatian Open Data Pipeline — CLAUDE.md

## Project Overview

An automated ETL pipeline that ingests public datasets from data.gov.hr (Croatian
Open Data Portal), normalizes them into a PostgreSQL data warehouse, and exposes
them through a REST API and dashboard.

**Core data engineering principle:** Only pull what changed. Never re-download
a full dataset if only a few rows changed. This is achieved through hash-based
incremental loading.

**Primary dataset for MVP:** Registar udruga Republike Hrvatske (NGO Registry)
— 50MB+ JSON, daily refresh, covers all Croatian counties. Expandable to other
datasets through the same connector architecture.

---

## Tech Stack

| Layer        | Technology                              |
|--------------|-----------------------------------------|
| Ingestion    | Python (requests, httpx)               |
| Transformation | Python (pandas, pydantic)             |
| Orchestration | APScheduler (simple) or Prefect (advanced) |
| Database     | PostgreSQL 15+                         |
| API          | FastAPI                                 |
| Frontend     | Next.js 14 (App Router) + Tailwind CSS  |
| Deployment   | Docker Compose                          |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Scheduler (daily/hourly)                 │
└──────────────────────┬──────────────────────────────────────┘
                       │ triggers
┌──────────────────────▼──────────────────────────────────────┐
│                   Orchestrator                              │
│              pipeline/orchestrator.py                       │
│                                                             │
│  1. Fetch dataset metadata from CKAN API                   │
│  2. Compare hash/last_modified with DB state               │
│  3. Dispatch only changed datasets to connectors           │
│  4. Mark deleted datasets                                   │
└──────┬───────────────┬────────────────────┬─────────────────┘
       │               │                    │
┌──────▼───┐    ┌──────▼───┐        ┌───────▼──┐
│ Udruge   │    │ Stranke  │        │ Kultura  │   ... (more connectors)
│Connector │    │Connector │        │Connector │
└──────┬───┘    └──────┬───┘        └───────┬──┘
       │               │                    │
       └───────────────┼────────────────────┘
                       │ normalized data
┌──────────────────────▼──────────────────────────────────────┐
│                    PostgreSQL                               │
│                                                             │
│   pipeline_runs      — audit log of every ETL run          │
│   dataset_registry   — CKAN dataset metadata + hash state  │
│   udruge             — NGO data (normalized)               │
│   stranke            — political parties                    │
│   kulturna_dobra     — cultural heritage                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              FastAPI + Next.js Dashboard                    │
│  - Dataset freshness status                                 │
│  - Row counts and change history                            │
│  - Search and filter across datasets                        │
│  - Pipeline run logs                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Pattern: Hash-Based Incremental Load

This is the heart of the project. Never download a full file if only metadata changed.

### Step 1 — Dataset-level change detection

CKAN API returns `hash` (MD5 of file contents) and `last_modified` for every resource.
Compare against what we have stored in `dataset_registry`.

```python
# pipeline/change_detector.py

def get_changed_datasets(ckan_datasets: list[dict]) -> dict:
    """
    Returns:
        {
            "new":      [dataset, ...],   # never seen before
            "changed":  [dataset, ...],   # hash is different
            "deleted":  [dataset_id, ...] # was in DB, not in CKAN anymore
            "unchanged":[dataset, ...],   # hash matches, skip
        }
    """
    stored = db.query("SELECT ckan_id, file_hash FROM dataset_registry")
    stored_map = {row.ckan_id: row.file_hash for row in stored}
    ckan_ids = set()

    result = {"new": [], "changed": [], "deleted": [], "unchanged": []}

    for dataset in ckan_datasets:
        ckan_id = dataset["id"]
        ckan_hash = dataset.get("hash", "")
        ckan_ids.add(ckan_id)

        if ckan_id not in stored_map:
            result["new"].append(dataset)
        elif stored_map[ckan_id] != ckan_hash:
            result["changed"].append(dataset)
        else:
            result["unchanged"].append(dataset)

    # Find deleted — in DB but not in CKAN anymore
    result["deleted"] = [
        ckan_id for ckan_id in stored_map
        if ckan_id not in ckan_ids
    ]

    return result
```

### Step 2 — Row-level upsert inside changed dataset

When a dataset's hash has changed, we download the file and upsert only the
rows that are actually different using row-level hashing.

```python
# pipeline/loader.py

def upsert_rows(df: pd.DataFrame, table: str, pk_column: str):
    """
    For each row:
    - Compute MD5 hash of all column values
    - INSERT ... ON CONFLICT (pk) DO UPDATE only if hash changed
    - Rows not in new data get soft-deleted (deleted_at = now())
    """

    # Add row hash for change detection
    df["row_hash"] = df.apply(
        lambda row: hashlib.md5(
            str(row.values).encode()
        ).hexdigest(),
        axis=1
    )

    # Upsert via raw SQL for performance
    upsert_sql = f"""
        INSERT INTO {table} ({', '.join(df.columns)}, updated_at)
        VALUES %s
        ON CONFLICT ({pk_column})
        DO UPDATE SET
            {', '.join(f'{col} = EXCLUDED.{col}' for col in df.columns if col != pk_column)},
            updated_at = now()
        WHERE {table}.row_hash != EXCLUDED.row_hash
    """
    # execute_values(cursor, upsert_sql, df.values.tolist())

def soft_delete_missing(table: str, pk_column: str, active_ids: list):
    """Mark rows deleted in source as deleted locally. Never hard delete."""
    db.execute(f"""
        UPDATE {table}
        SET deleted_at = now()
        WHERE {pk_column} NOT IN %(active_ids)s
        AND deleted_at IS NULL
    """, {"active_ids": tuple(active_ids)})
```

### Step 3 — Audit trail

Every pipeline run is logged regardless of outcome.

```python
# Every run creates a record:
{
    "run_id": "uuid",
    "started_at": "2026-04-09T08:00:00",
    "finished_at": "2026-04-09T08:01:23",
    "status": "success|partial|failed",
    "datasets_checked": 10,
    "datasets_changed": 2,
    "datasets_unchanged": 8,
    "datasets_deleted": 0,
    "rows_inserted": 145,
    "rows_updated": 23,
    "rows_deleted": 4,
    "error_message": null
}
```

---

## Database Schema

```sql
-- Tracks CKAN dataset state for incremental loading
CREATE TABLE dataset_registry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ckan_id         TEXT UNIQUE NOT NULL,
    ckan_name       TEXT NOT NULL,
    title           TEXT,
    organization    TEXT,
    file_hash       TEXT,           -- last known MD5 from CKAN
    last_modified   TIMESTAMPTZ,    -- last_modified from CKAN resource
    last_synced_at  TIMESTAMPTZ,    -- when WE last processed it
    refresh_freq    TEXT,           -- 'daily', 'weekly', etc.
    row_count       INTEGER,
    status          TEXT DEFAULT 'active',  -- active | deleted
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Audit log for every pipeline execution
CREATE TABLE pipeline_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_type            TEXT,           -- 'scheduled' | 'manual'
    started_at          TIMESTAMPTZ NOT NULL,
    finished_at         TIMESTAMPTZ,
    status              TEXT,           -- 'success' | 'partial' | 'failed'
    datasets_checked    INTEGER DEFAULT 0,
    datasets_changed    INTEGER DEFAULT 0,
    datasets_unchanged  INTEGER DEFAULT 0,
    rows_inserted       INTEGER DEFAULT 0,
    rows_updated        INTEGER DEFAULT 0,
    rows_soft_deleted   INTEGER DEFAULT 0,
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

-- NGO Registry (primary MVP dataset)
CREATE TABLE udruge (
    id                  TEXT PRIMARY KEY,   -- CKAN internal ID
    naziv               TEXT,
    skraceni_naziv      TEXT,
    oib                 TEXT,
    zupanija            TEXT,
    grad                TEXT,
    adresa              TEXT,
    datum_osnivanja     DATE,
    datum_brisanja      DATE,
    djelatnosti         JSONB,          -- nested array stays as JSONB
    row_hash            TEXT,           -- MD5 of all columns for change detection
    source_dataset_id   TEXT REFERENCES dataset_registry(ckan_id),
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ,
    deleted_at          TIMESTAMPTZ     -- soft delete, never hard delete
);

CREATE INDEX idx_udruge_zupanija ON udruge(zupanija);
CREATE INDEX idx_udruge_datum_osnivanja ON udruge(datum_osnivanja);
CREATE INDEX idx_udruge_deleted ON udruge(deleted_at) WHERE deleted_at IS NULL;
```

---

## Project Structure

```
hr-open-data-pipeline/
│
├── pipeline/                         # Core ETL logic
│   ├── orchestrator.py               # Main entry point, coordinates everything
│   ├── ckan_client.py                # CKAN API wrapper
│   ├── change_detector.py            # Hash comparison, what changed?
│   ├── loader.py                     # Upsert logic, soft deletes
│   ├── scheduler.py                  # APScheduler setup
│   └── connectors/
│       ├── base.py                   # Abstract base connector
│       ├── udruge.py                 # NGO registry connector
│       ├── stranke.py                # Political parties connector
│       └── kulturna_dobra.py         # Cultural heritage connector
│
├── api/                              # FastAPI backend
│   ├── main.py
│   └── routers/
│       ├── datasets.py               # Dataset metadata endpoints
│       ├── udruge.py                 # NGO search/filter endpoints
│       ├── pipeline.py               # Pipeline run history, trigger manual run
│       └── health.py
│
├── frontend/                         # Next.js dashboard
│   └── app/
│       ├── page.tsx                  # Overview: dataset freshness cards
│       ├── pipeline/page.tsx         # Run history, delta stats
│       └── explore/[dataset]/page.tsx # Browse/search dataset contents
│
├── database.py                       # SQLAlchemy setup
├── docker-compose.yml
├── .env.example
└── CLAUDE.md
```

---

## CKAN Client

```python
# pipeline/ckan_client.py

BASE_URL = "https://data.gov.hr/ckan/api/3/action"

class CKANClient:

    def get_all_datasets(self, rows_per_page=100) -> list[dict]:
        """Paginate through ALL datasets on data.gov.hr"""
        all_datasets = []
        offset = 0

        while True:
            resp = requests.get(f"{BASE_URL}/package_search", params={
                "rows": rows_per_page,
                "start": offset,
                "sort": "metadata_modified desc"
            })
            data = resp.json()["result"]
            all_datasets.extend(data["results"])

            if offset + rows_per_page >= data["count"]:
                break
            offset += rows_per_page

        return all_datasets

    def get_resource_data(self, resource_id: str, use_datastore: bool = True):
        """
        If datastore_active=True → use datastore_search API (paginated, no full download)
        If not → download the raw file (CSV/JSON)

        datastore_search is MUCH better — it's like a SQL query on CKAN's DB.
        Supports filters, sorting, field selection.
        """
        if use_datastore:
            return self._datastore_search(resource_id)
        else:
            return self._download_file(resource_id)

    def _datastore_search(self, resource_id: str, limit=10000):
        """Query CKAN datastore directly — no full file download"""
        all_records = []
        offset = 0

        while True:
            resp = requests.get(f"{BASE_URL}/datastore_search", params={
                "resource_id": resource_id,
                "limit": limit,
                "offset": offset
            })
            result = resp.json()["result"]
            all_records.extend(result["records"])

            if len(result["records"]) < limit:
                break
            offset += limit

        return all_records
```

**Important:** Many resources in data.gov.hr have `datastore_active: True` — for
those we can query the datastore directly instead of downloading the full file.
This is faster and more efficient. Always prefer this when available.

---

## Connector Pattern

Each dataset gets its own connector that handles schema-specific transformation.

```python
# pipeline/connectors/base.py

class BaseConnector(ABC):
    dataset_name: str       # CKAN dataset name slug
    target_table: str       # PostgreSQL table to write to
    primary_key: str        # Column used for upsert conflict resolution

    @abstractmethod
    def transform(self, raw_records: list[dict]) -> pd.DataFrame:
        """Clean and normalize raw CKAN records into target schema"""
        pass

    def run(self):
        """Standard run — same for all connectors"""
        raw = ckan_client.get_resource_data(self.resource_id)
        df = self.transform(raw)
        loader.upsert_rows(df, self.target_table, self.primary_key)
        loader.soft_delete_missing(self.target_table, self.primary_key, df[self.primary_key].tolist())


# pipeline/connectors/udruge.py

class UdrugeConnector(BaseConnector):
    dataset_name = "registar-udruga"
    target_table = "udruge"
    primary_key = "id"

    def transform(self, raw_records: list[dict]) -> pd.DataFrame:
        df = pd.DataFrame(raw_records)

        # Rename CKAN field names to our schema
        df = df.rename(columns={
            "OIB": "oib",
            "Naziv": "naziv",
            "Županija": "zupanija",
            "DatumOsnivanja": "datum_osnivanja",
        })

        # Parse dates
        df["datum_osnivanja"] = pd.to_datetime(df["datum_osnivanja"], errors="coerce")

        # Normalize county names (CKAN has inconsistencies)
        df["zupanija"] = df["zupanija"].str.strip().str.title()

        # Keep djelatnosti as JSON string
        df["djelatnosti"] = df["djelatnosti"].apply(json.dumps)

        return df[["id", "naziv", "oib", "zupanija", "grad", "adresa",
                   "datum_osnivanja", "datum_brisanja", "djelatnosti"]]
```

---

## Scheduling

```python
# pipeline/scheduler.py

from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()

# Run full pipeline every day at 06:00
@scheduler.scheduled_job("cron", hour=6, minute=0)
def daily_sync():
    orchestrator.run(run_type="scheduled")

# Health check every hour — just check if data.gov.hr is reachable
@scheduler.scheduled_job("interval", hours=1)
def health_check():
    orchestrator.check_source_health()
```

---

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/hr_open_data

# CKAN
CKAN_BASE_URL=https://data.gov.hr/ckan/api/3/action

# Scheduling
SYNC_HOUR=6
SYNC_MINUTE=0

# Logging
LOG_LEVEL=INFO
```

---

## MVP Scope

### Must have
- [ ] CKAN client with full pagination
- [ ] Hash-based change detection at dataset level
- [ ] Udruge connector (full transform + upsert)
- [ ] Soft delete for removed records
- [ ] pipeline_runs audit log
- [ ] FastAPI endpoint: GET /api/datasets (list with freshness status)
- [ ] FastAPI endpoint: GET /api/udruge (search by county, name)
- [ ] FastAPI endpoint: POST /api/pipeline/run (manual trigger)
- [ ] Basic Next.js dashboard showing dataset cards with last sync time

### Nice to have
- [ ] Row-level hash for granular change detection
- [ ] Stranke connector (political parties)
- [ ] Kulturna dobra connector (cultural heritage)
- [ ] Email/webhook alert when sync fails
- [ ] Delta stats chart (rows added/updated/deleted over time)

### Out of scope for MVP
- [ ] Real-time streaming
- [ ] Multi-user auth
- [ ] Custom dataset request from users

---

## Development Setup

```bash
# Clone and setup
git clone <repo>
cd hr-open-data-pipeline

# Start Postgres
docker-compose up -d postgres

# Run migrations
python database.py migrate

# Backend
cd api
pip install -r requirements.txt
uvicorn main:app --reload

# Run pipeline manually (test)
python -m pipeline.orchestrator --run-once

# Scheduler (production)
python -m pipeline.scheduler

# Frontend
cd frontend
npm install && npm run dev
```

---

## Key Design Decisions

**Why soft delete instead of hard delete?**
Because a record disappearing from CKAN doesn't always mean it's truly gone —
sometimes it's a temporary API issue. Soft delete lets us recover and gives us
a complete historical record of every entity.

**Why row-level hashing?**
A dataset's file hash changes even if only 1 row changed. Without row-level
hashing we'd re-upsert all 50k+ rows every time. With row hashing, the
`ON CONFLICT DO UPDATE WHERE hash != EXCLUDED.hash` clause skips unchanged rows
at the database level — very fast.

**Why datastore_search over file download?**
For resources with `datastore_active: True`, CKAN's datastore_search API lets
us paginate and filter at the source. We never download a 50MB file if we only
need 100 changed records.

---

*Built for Innovative Project course — Algebra Bernays University*
*Stack: Python · FastAPI · PostgreSQL · Next.js · data.gov.hr CKAN API*
