# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Start both services (recommended)
```bash
./start.sh
```

### Backend only
```bash
cd backend
.venv/bin/uvicorn main:app --reload --port 8000
```

### Frontend only
```bash
cd frontend
npm run dev
```

### Frontend build
```bash
cd frontend
npm run build
```

### Install dependencies
```bash
# Backend
cd backend && pip install -r requirements.txt

# Frontend
cd frontend && npm install
```

## Architecture

This is a **FastAPI + React 18** pharma sales intelligence dashboard for IVC Ivory Coast Q1 2026.

### Backend (`backend/`)

**Startup flow** (`main.py`):
1. `lifespan()` runs on startup, loading all Excel data into `app_state["data"]`
2. Data is structured as `app_state["data"][month_key][data_type]` where `month_key` ∈ `{"jan", "feb", "mar"}` and `data_type` ∈ `{"sales", "projection", "expense", "monthly", "copy", "tour", "visits"}`
3. If Redis is available, all endpoints are eagerly pre-computed and cached
4. Routers are registered under `/api` prefix

**Storage backends** (selectable via `STORAGE_BACKEND` env var):
- `local` (default): reads from `IVC/` folder on disk via `storage/local.py`
- `sheets`: reads from Google Sheets via `storage/sheets.py` using gspread; requires `GOOGLE_CREDENTIALS_JSON` and `GOOGLE_DRIVE_FOLDER_ID`
- `s3`: stub in `storage/s3.py`, not yet implemented

Both paths feed the same loader functions in `loaders.py`. The local path passes `file_bytes=`, the Sheets path passes `df=` (a pre-fetched DataFrame).

**Caching** (`cache/redis_client.py`):
- Redis is optional — the app works without it, just slower
- API results cached under keys like `api:overview`, `api:months:jan`, etc.
- Sheet metadata (Drive `modifiedTime`) cached under `sheets:{id}:drive_modified` with 25-hour TTL
- `SHEET_DEPENDENCIES` dict maps each source sheet key to the list of API endpoints that must be invalidated when that sheet changes
- `POST /api/data/refresh` checks Drive modified times, only re-fetches changed sheets, then invalidates and eagerly recomputes affected endpoints

**Loaders** (`loaders.py`):
- All loaders accept either `file_bytes=` (local) or `df=` (Sheets) — never both
- `load_all_data(storage)` is the local-mode entry point; `load_all_from_sheets(storage)` is the Sheets-mode entry point (in `sheets_loader.py`)
- NaN/Inf floats are globally sanitized to `null` via `NaNSafeJSONResponse` in `main.py`

**Name normalization** (`name_map.py`):
- `normalize_mr()` / `mr_display_name()` — fuzzy-matches delegate names to canonical IDs
- `normalize_product()` / `product_display_name()` — canonicalizes product names
- `normalize_activity()` / `normalize_doctor()` / `normalize_territory()` — same pattern
- `build_doctor_index()` — must be called after loading data to enable doctor fuzzy matching

**Routers** (`routers/`): Each router reads from `app_state["data"]`, checks Redis cache first, computes the result, stores it, then returns. Pattern is consistent across all 6 routers.

**AI Insights** (`insights_builder.py`): Calls Groq API (`llama-3.1-8b-instant`) with a prompt built from the loaded data. Cached in both `app_state["insights_cache"]` and Redis.

### Frontend (`frontend/src/`)

**Data fetching** (`hooks/useDashboard.js`): All API calls go through TanStack Query hooks. The `baseURL` is `/api` — Vite proxies this to `localhost:8000` in dev (see `vite.config.js`).

**Tab structure** (`App.jsx`): Seven tabs rendered as panels; only the active tab fetches and renders. Tabs: `ov` (Overview), `jan`, `feb`, `mar`, `prod` (Products), `del` (Delegates), `exp` (Expenses).

**Charts**: All charts use Chart.js 4 via `react-chartjs-2`. Reusable config helpers in `utils/chartConfig.js`. Month-specific config (colors, labels) in `utils/monthConfig.js`.

**Components** (`components/`): `KpiCard`, `ChartCard`, `DataTable`, `InsightBox`, `Badge`, `SectionLabel`, `TabBar` — all purely presentational.

### Data files (`IVC/`)

```
IVC/
├── IVC_Sales_2026.xlsx          # Master sales file with tabs per month (JAN-26, FEB-26, MAR-26)
├── Jan/                         # January per-month files
│   ├── IVC_Projection_Jan_2026.xlsx
│   ├── IVC_Expense_Jan_2026.xlsx
│   ├── IVC_Monthly_Reports_Jan_2026.xlsx
│   ├── IVC_Tour_Plan_Jan_2026.xlsx
│   └── IVC_Visit_Tracker_Jan_2026.xlsx
├── Feb/                         # Same structure for February
└── March/                       # Same structure for March
```

There is also a Copy Report file (`IVC_Copy_Of_Report_2026.xlsx` or similar) with one tab per month.

### Environment variables (`backend/.env`)

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Required for AI insights |
| `STORAGE_BACKEND` | `local` or `sheets` |
| `IVC_DATA_PATH` | Path to `IVC/` folder (local mode) |
| `GOOGLE_CREDENTIALS_JSON` | Full service-account JSON as a single line (sheets mode) |
| `GOOGLE_DRIVE_FOLDER_ID` | Drive folder containing all IVC spreadsheets (sheets mode) |
| `REDIS_URL` | Redis connection string (optional, defaults to `redis://localhost:6379`) |

### Key constants (`backend/constants.py`)

- `FCFA_TO_EUR = 655.97` — currency conversion rate
- `DISTRIBUTORS` — list of 4 distributor names used as column prefixes in sales data
- `_NON_MR_IDS` — IDs excluded from MR Performance tab
