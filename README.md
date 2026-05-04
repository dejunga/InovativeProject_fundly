# InovativeProject Fundly — HR Open Data Platform

A data pipeline and web app that syncs NGO registry and funding data from [data.gov.hr](https://data.gov.hr) into a local PostgreSQL database, with a REST API and Next.js frontend.

## Architecture

```
data.gov.hr (CKAN) → Python pipeline → PostgreSQL → FastAPI → Next.js frontend
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 14+

---

## 1. Clone the repository

```bash
git clone https://github.com/dejunga/InovativeProject_fundly.git
cd InovativeProject_fundly
```

---

## 2. Set up PostgreSQL

Run the two commands **separately** — `CREATE DATABASE` cannot run in the same transaction as `CREATE USER`:

**Windows (PowerShell):**
```powershell
$env:PGPASSWORD = "your_postgres_password"
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "CREATE USER antonio WITH PASSWORD 'password';"
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "CREATE DATABASE hr_open_data OWNER antonio;"
```

**macOS / Linux:**
```bash
psql -U postgres -c "CREATE USER antonio WITH PASSWORD 'password';"
psql -U postgres -c "CREATE DATABASE hr_open_data OWNER antonio;"
```

Or use any existing user — just update the `.env` accordingly.

---

## 3. Configure environment variables

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/hr_open_data
CKAN_BASE_URL=https://data.gov.hr/ckan/api/3/action
SYNC_HOUR=6
SYNC_MINUTE=0
LOG_LEVEL=INFO
```

---

## 4. Set up the Python backend

```bash
# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Run database migrations

```bash
python database.py
```

This creates all required tables (`dataset_registry`, `pipeline_runs`, `udruge`, `financijske_potpore`).

### Run the data pipeline (first sync)

```bash
python -m pipeline.orchestrator
```

### Start the API server

```bash
uvicorn api.main:app --reload
```

API will be available at `http://localhost:8000`  
Interactive docs at `http://localhost:8000/docs`

---

## 5. Set up the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at `http://localhost:3000`

---

## Project structure

```
├── api/                  # FastAPI application
│   ├── main.py
│   └── routers/          # Endpoints: datasets, udruge, financiranje, pipeline, health
├── pipeline/             # Data sync pipeline
│   ├── orchestrator.py   # Entry point
│   ├── ckan_client.py    # data.gov.hr API client
│   ├── change_detector.py
│   ├── loader.py         # DB upsert/soft-delete logic
│   └── connectors/       # Per-dataset transform logic
├── frontend/             # Next.js app
│   └── app/
├── database.py           # Schema migrations
└── requirements.txt
```

---

## Running everything at once

You need three terminals:

**Terminal 1 — API**
```bash
.venv\Scripts\activate   # or: source .venv/bin/activate
uvicorn api.main:app --reload
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
```

**Terminal 3 — Pipeline (optional, run manually to sync data)**
```bash
.venv\Scripts\activate
python -m pipeline.orchestrator
```
