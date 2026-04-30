# IVC Deep Analysis Dashboard 2026

A full-stack pharma sales intelligence dashboard for IVC Ivory Coast Q1 2026, built with **FastAPI** + **React 18 + Vite**.

## Overview

Aggregates 18+ Excel source files across January, February, and March 2026:
- Sales data (per distributor and product)
- Monthly delegate performance reports
- Activity & expense sheets
- Visit trackers
- Projection & activity plans
- Tour plans

Powered by **Groq AI** for automated insights using `llama-3.1-8b-instant`.

## Prerequisites

- Python 3.11+
- Node.js 18+
- A [Groq API key](https://console.groq.com/) (free tier available)

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd ivc-sales-dashboard
```

> **Note:** The `IVC/` data folder must be present at the repo root: `ivc-sales-dashboard/IVC/`

### 2. Backend setup

```bash
cd backend
pip install -r requirements.txt
```

Copy the example env file and add your Groq key:

```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY=your_actual_key
```

Or edit `.env` directly:
```
GROQ_API_KEY=your_key_here
STORAGE_BACKEND=local
IVC_DATA_PATH=../IVC
```

### 3. Frontend setup

```bash
cd frontend
npm install
```

## Running

Start both services in separate terminals:

**Terminal 1 — Backend:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

## Dashboard Tabs

| Tab | Description |
|-----|-------------|
| 📊 Q1 Overview | Month comparison trio, product mix evolution, AI insights |
| 🔵 January | Full January KPIs, target vs achieved, delegate table, expenses |
| 🟡 February | February data with stacked call breakdown, Valery new delegate |
| 🟢 March | March data with CTC ratio chart (25% reference line) |
| 📦 Products | Q1 trend, annual vs Q1 achievement, category doughnut |
| 👥 Delegates | Cross-month visit counts, orders, avg calls/day, CTC ratios |
| 💰 Expenses | Budget flow, spend rate, activity type distribution |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check |
| `GET /api/overview` | Q1 summary + month comparison |
| `GET /api/months/{jan\|feb\|mar}` | Full monthly data bundle |
| `GET /api/products` | Product Q1 trend + annual target |
| `GET /api/delegates` | Cross-month MR performance |
| `GET /api/expenses` | Budget flow + activity expenses |
| `GET /api/insights` | AI-generated insights (cached) |
| `POST /api/insights/refresh` | Force regenerate insights from Groq |

## Storage Architecture

The app uses an abstract `StorageBackend` pattern:

- **Currently active:** `LocalStorage` — reads from `IVC/` on disk
- **Future:** `S3Storage` stub available in `backend/storage/s3.py`

To migrate to AWS S3:
1. Implement `backend/storage/s3.py` using boto3
2. Set `STORAGE_BACKEND=s3` and `S3_BUCKET_NAME=your-bucket` in `.env`

## Tech Stack

- **Backend:** Python 3.11, FastAPI, pandas, openpyxl, rapidfuzz, groq, uvicorn
- **Frontend:** React 18, Vite, Chart.js 4, react-chartjs-2, @tanstack/react-query, axios
- **AI:** Groq llama-3.1-8b-instant
- **No:** Streamlit, SQLAlchemy, Redux, Tailwind, React Router
