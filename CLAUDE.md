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

This is a **FastAPI + React 18** pharma sales intelligence dashboard for IVC Ivory Coast 2026.

### Backend (`backend/`)

**Startup flow** (`main.py`):
1. `lifespan()` runs on startup, selects storage backend, and loads all data into `app_state["data"]`
2. Data is structured as `app_state["data"][month_key][data_type]` where `month_key` is dynamic (e.g. `"jan"`, `"feb"`, `"mar"`, …) and `data_type` ∈ `{"sales", "projection", "expense", "monthly", "tour", "visits"}` (plus `"copy"` in local mode)
3. If Redis is available, all endpoints are eagerly pre-computed and cached
4. Routers are registered under `/api` prefix

**Storage backends** (selectable via `STORAGE_BACKEND` env var):
- `local` (default): reads from `IVC/` folder on disk via `storage/local.py`
- `sheets`: reads from Google Sheets via `storage/sheets.py` using gspread; requires `GOOGLE_CREDENTIALS_JSON` and `GOOGLE_DRIVE_FOLDER_ID`
- `s3`: stub in `storage/s3.py`, not yet implemented

Both paths feed the same loader functions in `loaders.py`. The local path passes `file_bytes=`, the Sheets path passes `df=` (a pre-fetched DataFrame).

**Dynamic month discovery** (sheets mode, `sheets_loader.py`):
- `MONTHS` is a module-level `list[dict]` built at startup via `init_months_config()` — must be called before `load_all_from_sheets()`
- Months are discovered by scanning Drive folder (`storage/sheet_discovery.py`) and inspecting sales spreadsheet tab names (`JAN-26`, `FEB-26`, etc.)
- `MONTHS` is cached in Redis under `config:months_config` (26h TTL) to avoid extra API calls on restarts
- Each entry carries keys: `key`, `sales_tab`, `prev_sales_tab`, `expense_key`, `monthly_key`, `projection_key`, `tour_key`, `visits_key`, `visits_label`, `label`

**Batch fetching** (`sheets_loader.py`):
- Each spreadsheet uses `spreadsheets.values.batchGet` — 2 API calls per spreadsheet (open + batchGet)
- `_open_and_batch_fetch()` checks Drive `modifiedTime` against Redis before opening; returns `({}, mod, True)` on a cache HIT (sheet unchanged)
- Rate-limit errors (HTTP 429) trigger exponential backoff: 15s, 30s, 60s up to 4 retries

**Caching** (`cache/redis_client.py`):
- Redis is optional — the app works without it, just slower
- API results cached under keys like `api:overview`, `api:months:jan`, etc.
- Sheet metadata (Drive `modifiedTime`) cached under `sheets:{id}:drive_modified` with 25-hour TTL
- `build_sheet_dependencies(month_keys)` builds the sheet→API-endpoint dependency map dynamically; result stored in `app_state["sheet_dependencies"]`
- `POST /api/data/refresh` checks Drive modified times, only re-fetches changed sheets, then invalidates and eagerly recomputes affected endpoints
- `_has_shell_data()` in `main.py` detects when `app_state["data"]` holds only an empty shell (server started entirely from Redis cache) and forces a full Drive reload on the first `/api/data/refresh`

**Loaders** (`loaders.py`):
- All loaders accept either `file_bytes=` (local) or `df=` (Sheets) — never both
- `load_all_data(storage)` is the local-mode entry point; `load_all_from_sheets(storage)` is the Sheets-mode entry point (in `sheets_loader.py`)
- Tab name aliases are handled in `sheets_loader.py` — both old names (`"ACTIVITY EXP."`, `"Delegates Reports"`) and new names (`"ACTIVITY EXPENSES"`, `"DELEGATES"`) are tried via `_get_first()`
- NaN/Inf floats are globally sanitized to `null` via `NaNSafeJSONResponse` in `main.py`

**Name normalization** (`name_map.py`):
- `normalize_mr()` / `mr_display_name()` — fuzzy-matches delegate names to canonical IDs (`MR_001`–`MR_006`, `AGT_001`)
- `normalize_product()` / `product_display_name()` — canonicalizes product names
- `normalize_activity()` / `normalize_doctor()` / `normalize_territory()` — same pattern
- `build_doctor_index()` — must be called after loading data to enable doctor fuzzy matching

**Routers** (`routers/`): 7 routers — `overview`, `months`, `products`, `delegates`, `expenses`, `activities`, `insights`. Each checks Redis cache first, computes, stores, then returns. Pattern is consistent across all routers.

**AI Insights** (`insights_builder.py`): Calls Groq API (`llama-3.1-8b-instant`) with a prompt built from the loaded data. Cached in both `app_state["insights_cache"]` and Redis.

**Key endpoints**:
- `GET /api/health` — returns `{"status": "ok", "months_loaded": [...]}`
- `GET /api/months` — returns list of currently loaded month keys
- `GET /api/months/{month}` — full monthly data bundle (KPIs, sales, delegates, expenses, tour plan, visit tracker)
- `POST /api/data/refresh` — re-checks Drive for changes, refreshes only what changed
- `GET /api/cache/redisStatus` — Redis health and cached endpoint count

### Frontend (`frontend/src/`)

**Data fetching** (`hooks/useDashboard.js`): All API calls go through TanStack Query hooks. The `baseURL` is `/api` — Vite proxies this to `localhost:8000` in dev. `useAvailableMonths()` fetches from `GET /api/health` and returns `months_loaded`.

**Tab structure** (`App.jsx`): Tabs are dynamic — static tabs `ov`, `prod`, `del`, `exp`, `act` are always present; month tabs are inserted between `ov` and `prod` based on `useAvailableMonths()`. Only the active tab renders. Month tabs render `<MonthTab month={key} />`.

**Charts**: All charts use Chart.js 4 via `react-chartjs-2`. Reusable config helpers in `utils/chartConfig.js`. Month-specific config (colors, labels) in `utils/monthConfig.js`.

**Components** (`components/`): `KpiCard`, `ChartCard`, `DataTable`, `InsightBox`, `Badge`, `SectionLabel`, `TabBar`, `SalesOutcomeCell`, `TourPlanSection`, `VisitTrackerSection` — all purely presentational.

### Data files (`IVC/`)

```
IVC/
├── IVC_Sales_2026.xlsx          # Master sales file with one tab per month (JAN-26, FEB-26, …)
├── IVC_Copy_Of_Report_2026.xlsx # Copy report, one tab per month (local mode only)
├── Jan/
│   ├── IVC_Projection_Jan_2026.xlsx
│   ├── IVC_Expense_Jan_2026.xlsx
│   ├── IVC_Monthly_Reports_Jan_2026.xlsx
│   ├── IVC_Tour_Plan_Jan_2026.xlsx
│   └── IVC_Visit_Tracker_Jan_2026.xlsx
├── Feb/                         # Same structure
└── March/                       # Same structure
```

In Sheets mode, the Drive folder is scanned recursively; subfolders like `Jan/`, `Feb/`, `March/` are walked automatically. New month folders added to Drive are auto-detected on next startup or refresh.

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
- `DISTRIBUTORS` — list of 4 distributor names used as column prefixes in sales data (`UBIPHARM/LABOREX`, `COPHARMED/LABOREX`, `TEDIS`, `DPCI`)
- `_NON_MR_IDS` — IDs excluded from MR Performance tab (`MR_006`, `AGT_001`, `UNKNOWN`)
