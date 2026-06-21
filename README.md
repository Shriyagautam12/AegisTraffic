# 🛡️ AegisTraffic — AI Traffic Command System for Bengaluru City Police

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/FastAPI-0.110-green?style=for-the-badge&logo=fastapi" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react" />
  <img src="https://img.shields.io/badge/LightGBM-ML%20Engine-orange?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Gemini-2.5%20Flash-purple?style=for-the-badge&logo=google" />
</p>

> **AegisTraffic** is a full-stack, AI-powered traffic command decision-support system built for the Bengaluru City Traffic Police. It combines machine learning prediction, historical incident retrieval, deterministic resource planning, a Gemini-powered AI copilot, and a human-in-the-loop post-event learning loop — all in a single operational dashboard.

---

## 📋 Table of Contents

1. [Problem Statement](#-problem-statement)
2. [Solution Overview](#-solution-overview)
3. [System Architecture](#-system-architecture)
4. [Tech Stack](#-tech-stack)
5. [Module Breakdown](#-module-breakdown)
6. [ML Models](#-ml-models)
7. [Frontend Features](#-frontend-features)
8. [API Reference](#-api-reference)
9. [Database Schema](#-database-schema)
10. [Setup & Installation](#-setup--installation)
11. [Running the Application](#-running-the-application)
12. [Training the Models](#-training-the-models)
13. [Project Structure](#-project-structure)
14. [Configuration & Environment](#-configuration--environment)

---

## 🚨 Problem Statement

Bengaluru's traffic police face three operational gaps:

| Gap | Impact |
|---|---|
| **Reactive response** | Officers respond after congestion forms, not before |
| **No data-driven resource allocation** | Deployment decisions rely on gut feel, not historical evidence |
| **No post-event learning** | After an event closes, nothing is captured; the same mistakes repeat |

AegisTraffic addresses all three by providing **predictive**, **evidence-grounded**, and **self-improving** operational intelligence.

---

## 💡 Solution Overview

AegisTraffic is built around **7 core modules** that work together:

```
Raw Incident Data (8,173 records)
        │
        ▼
┌──────────────────┐
│  Data Pipeline   │  Feature engineering, labelling, normalization
└──────┬───────────┘
       │
       ├──▶  Module 1: Historical Intelligence Engine  ──▶  Corridor risk, hotspots, temporal patterns
       ├──▶  Module 2: Impact Predictor (LightGBM)    ──▶  Severity (High/Med/Low) + Duration estimate
       ├──▶  Module 3: Similar Event Retriever        ──▶  Cosine similarity over historical incidents
       ├──▶  Module 4: Resource Recommender           ──▶  Officers, Barricades, Patrol Jeeps, Tow, Vans
       ├──▶  Module 5: Visualizer                     ──▶  Heatmaps, charts, risk overlays
       ├──▶  Module 6: AI Copilot (Gemini RAG)        ──▶  Free-text Q&A + Full operational orders
       └──▶  Module 7: Post-Event Learning Engine     ──▶  Feedback loop, outcome logging, self-correction
```

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────┐
│           React Frontend (Vite)              │
│  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Risk Intel   │  │  Event Simulator     │  │
│  │ Dashboard    │  │  + Feedback Form     │  │
│  ├──────────────┤  ├──────────────────────┤  │
│  │  AI Copilot  │  │  Post-Event Learning │  │
│  └──────────────┘  └──────────────────────┘  │
└───────────────────┬─────────────────────────┘
                    │  HTTP / REST
                    ▼
┌─────────────────────────────────────────────┐
│           FastAPI Backend (uvicorn)          │
│                                             │
│  /api/overview   /api/simulate              │
│  /api/copilot    /api/learning              │
│  /api/learning/outcome                      │
└────────┬────────────────────┬───────────────┘
         │                    │
         ▼                    ▼
┌──────────────┐    ┌──────────────────────┐
│  ML Models   │    │    SQLite DB         │
│  (joblib)    │    │    learning.db       │
│  LightGBM ×4 │    │  predictions table   │
└──────────────┘    │  outcomes table      │
                    └──────────────────────┘
```

---

## 🛠️ Tech Stack

### Backend
| Component | Technology |
|---|---|
| API Framework | FastAPI + Uvicorn |
| ML Engine | LightGBM (4 models) |
| Explainability | SHAP |
| Vector Similarity | scikit-learn cosine similarity |
| AI Copilot | Google Gemini 2.5 Flash (RAG) |
| Database | SQLite (via Python `sqlite3`) |
| Data Processing | Pandas, NumPy |
| Model Serialization | Joblib |

### Frontend
| Component | Technology |
|---|---|
| Framework | React 18 + Vite |
| Styling | Vanilla CSS (glassmorphism + dark mode) |
| Maps | Leaflet.js + OSRM (live diversion routing) |
| Charts | SVG-based custom scatter plots |
| State Management | React hooks (useState, useEffect, useRef) |

---

## 📦 Module Breakdown

### Module 1 — Historical Intelligence Engine (`modules/intelligence.py`)
Pre-computes intelligence artifacts from 8,173 historical Bengaluru incidents:
- **Corridor risk index** — composite score from median closure time, high-severity rate, road closure rate
- **Junction hotspot scores** — ranked junctions with chronic chokepoint flags (median closure > 200 mins)
- **Temporal risk matrix** — 24h × 7d normalized activity heatmap (identifies morning 4–7 AM and evening 7–10 PM peaks)
- **Cause-zone affinity map** — top 3 event causes per Bengaluru zone for copilot context

### Module 2 — Impact Predictor (`modules/predictor.py`)
Inference engine using 4 trained LightGBM models:
- **Triage filter** — binary Low vs. not-Low (~90% accuracy); auto-clears minor incidents
- **Binary impact classifier** — detects High-severity (critical) events with optimized recall
- **3-class severity classifier** — Low / Medium / High for resource granularity
- **Duration regressor** — log-minutes regression to estimate clearance time in minutes

Returns: `severity`, `confidence`, `is_critical`, `duration_mins`, `duration_range`, `top_reasons` (SHAP), `probabilities`

### Module 3 — Similar Event Retriever (`modules/retrieval.py`)
Finds the K most similar historical incidents using cosine similarity over a weighted feature vector:

| Feature | Weight | Rationale |
|---|---|---|
| `cause_score` | 2.5 | Impact rank of event cause (most deterministic) |
| `corridor_tier` | 2.0 | Historical corridor risk level |
| `veh_risk` | 1.5 | Vehicle type risk score |
| `hour` | 1.5 | Time-of-day similarity |
| `road_closure_num` | 1.5 | Whether closure was required |
| `day_of_week` | 1.0 | Weekday pattern |
| `is_peak` | 0.5 | Peak hour overlap |

> **Design note**: Category codes (corridor_enc, cause_enc) are deliberately excluded — their integer values are arbitrary labels that inject meaningless cosine distance noise. A corridor prefilter handles exact match separately.

### Module 4 — Resource Recommender (`modules/recommender.py`)
Fully deterministic (no LLM) deployment plan generator:

**Event Tier base values:**

| Event Cause | Officers | Barricades | Tow |
|---|---|---|---|
| VIP Movement | 60 | 120 | 4 |
| Protest | 40 | 60 | 1 |
| Public Event | 30 | 60 | 2 |
| Procession | 25 | 35 | 1 |
| Accident | 6 | 6 | 2 |
| Construction | 4 | 8 | 1 |

**Scaling multipliers:**
- **Severity**: High ×1.0, Medium ×0.6, Low ×0.35
- **Corridor**: CBD ×1.30, ORR ×1.15, Standard ×1.00
- **Peak hours**: ×1.15
- **High priority**: ×1.15
- **Duration** (relief shifts): ≥8h ×1.6, 4–8h ×1.3, 2–4h ×1.1

Also computes: patrol jeeps, command vans, tow class (light/medium/heavy), special equipment, deployment junctions, owning police station.

### Module 5 — Visualizer (`modules/visualizer.py`)
Produces precomputed chart data for the frontend:
- Incident distribution by corridor, cause, severity
- Hourly/weekly temporal risk patterns
- Junction hotspot rankings

### Module 6 — AI Copilot (`modules/copilot.py`)
A **RAG (Retrieval-Augmented Generation)** pipeline powered by Gemini 2.5 Flash:

```
Free-text query (English/Kannada)
        │
        ▼
  Rule-based Parser
  (corridor, cause, hour, day extraction)
        │
        ▼
  Context Assembly (Modules 1–4)
  → prediction, precedent, resources, corridor intel
        │
        ▼
  Gemini 2.5 Flash
  (phrases the grounded context — never invents facts)
        │
        ▼
  Operational Briefing / Full Command Order
```

**Key principle**: Gemini only phrases and structures; all numbers, precedents, and junction names come from AegisTraffic's own modules. Falls back to a structured non-LLM response if offline.

**Full Operational Order mode** generates a DCP-level command order as structured JSON covering: personnel hierarchy, logistics, diversion legs, HGV bans, phased timeline (T-2h to Post), VMS advisory text.

### Module 7 — Post-Event Learning Engine (`modules/learning.py`)
Closes the feedback loop with a human-in-the-loop system:

- **`log_prediction()`** — records every simulation with predicted severity, duration, and all resource recommendations
- **`record_outcome()`** — records actual deployed resources (officers, barricades, patrol jeeps, tow vehicles, command vans), actual severity and clearance time
- **`get_correction_factor()`** — computes per-corridor duration correction factor from the median actual/predicted ratio (requires ≥5 outcomes; clamped to 0.5–2.0×)
- **`apply_correction()`** — applies the learned correction to future raw model predictions
- **`get_comparison_data()`** — returns predicted vs. actually deployed resources for the dashboard
- **`get_accuracy_report()`** — severity accuracy %, mean/median duration error in minutes

---

## 🤖 ML Models

### Training (`train_models.py`)

**Methodology — zero leakage, defense-ready:**
- Strict **temporal split**: Nov 2023 – Feb 2024 (train) / Mar–Apr 2024 (test)
- `corridor_risk_index` computed on **train only**, then mapped to test — no test signal bleeds into features
- Chronological validation fold (last 15% of train) for LightGBM early stopping

**Model files (saved to `models/`):**

| File | Description |
|---|---|
| `triage_clf.joblib` | Binary Low vs. not-Low classifier (~90% accuracy) |
| `impact_binary_clf.joblib` | Binary High vs. not-High classifier (critical detection) |
| `severity_clf.joblib` | 3-class LightGBM severity classifier |
| `duration_reg.joblib` | LightGBM log-minutes duration regressor |
| `encoders.joblib` | Categorical value→code mappings (built on train only) |
| `model_metadata.joblib` | All metrics, feature list, corridor risk lookup, train timestamp |

**Feature set:**

```python
FEATURE_COLS = [
    "cause_score", "corridor_tier", "veh_risk",
    "hour", "day_of_week", "month",
    "is_peak", "is_weekend", "is_planned",
    "requires_road_closure", "priority_num",
    "event_cause_enc", "corridor_enc", "zone_enc", "veh_type_enc",
    "corridor_risk_index"
]
```

---

## 🖥️ Frontend Features

### Tab 1 — Risk Intelligence Dashboard
- Live KPI cards: total incidents, high-severity %, median clearance, chronic junctions monitored
- Interactive Leaflet.js heatmap of all 8,173 incidents with severity/cause popups
- Corridor risk ranking table with sortable metrics
- Top junction hotspots with location and incident counts
- Cause distribution and severity breakdown charts
- Temporal activity level indicator (current IST hour/day)

### Tab 2 — Event Simulator
Multi-step form capturing:
- **Event Category** (Planned Event / Infrastructure & Hazards / Traffic Incidents) — hierarchical dropdown with search
- **Event Cause (Subcategory)** — searchable list per category; "Others (specify)" option
- **Corridor** — searchable dropdown with "Others (specify)" option
- **Vehicle Type, Date, Time, Duration, Road Closure toggle**

Generates:
- ML prediction (severity, confidence, clearance time, SHAP explanations, probabilities)
- Full resource deployment plan (personnel hierarchy, logistics, deployment junctions)
- Similar historical precedents (cosine similarity search)
- Optional live OSRM diversion route (fetched on demand)

**🔁 Operational Deployment Feedback card** (Human-in-the-Loop):
- Pre-filled editable inputs for Officers, Barricades, Patrol Jeeps, Tow Vehicles, Command Vans
- Real-time difference badges vs. suggested values (+N / −N)
- **Approve Suggested Plan** — active by default; disabled once any value is edited
- **Record Custom Deployment** — disabled by default; activates with a "Modified" badge upon any edit
- All submissions saved to SQLite and feed the learning engine

### Tab 3 — AI Copilot
- Free-text natural language interface (English and Kannada)
- Rule-based entity extraction (corridor, cause, hour, day) + Gemini LLM phrasing
- Full Command Order generation (DCP-style structured JSON rendered as operational briefing)
- Graceful offline fallback (structured non-LLM response)

### Tab 4 — Post-Event Learning
- **System Performance** KPIs: total predictions, outcomes recorded, severity accuracy %, median duration error
- **Predicted vs. Actual** SVG scatter plot (duration) with hover tooltips
- **🧠 Learned Corridor Corrections** — per-corridor duration multipliers learned from ≥5 outcomes
- **🔬 Comparative Analysis** — card-per-event layout showing predicted vs. actually deployed resources for all 5 resource types with color-coded diff badges:
  - ✓ Match (green) · +N over-deployed (red) · −N under-deployed (blue)
- **Manual outcome form** for simulating event closures on open predictions

---

## 🔌 API Reference

All endpoints served by FastAPI on port `8000`.

### `GET /api/overview`
Returns headline stats, model metrics, cause distribution, corridor list.

### `POST /api/simulate`
Runs a full event simulation.

**Request body:**
```json
{
  "event_cause": "public_event",
  "corridor": "Mysore Road",
  "veh_type": "bmtc_bus",
  "start_date": "2024-06-21",
  "start_time": "18:30",
  "duration_hrs": 3.0,
  "requires_road_closure": true,
  "event_category": "planned_event",
  "event_subcategory": "public_event"
}
```

**Response:** `{ prediction_id, event, prediction, resource_plan, precedents, diversion_plan }`

### `POST /api/simulate-narrative`
Generates a full DCP-style operational order (Gemini-powered).

**Request body:** `{ event: {...}, prediction: {...} }`

### `POST /api/copilot`
Natural language query.

**Request body:** `{ "query": "What resources do I need for a procession on Mysore Road at 6pm?" }`

**Response:** `{ answer, source, context, parsed }`

### `GET /api/learning`
Returns the full learning dashboard data.

**Response:**
```json
{
  "report": { "total_predictions", "total_outcomes", "severity_accuracy", "median_duration_error_mins" },
  "corrections": [{ "corridor", "correction_factor" }],
  "open_predictions": [...],
  "scatter_data": [...],
  "comparison_data": [...]
}
```

### `POST /api/learning/outcome`
Record an actual operational outcome (overwrites any existing for same prediction).

**Request body:**
```json
{
  "prediction_id": 35,
  "actual_severity": "High",
  "actual_duration": 180.0,
  "actual_officers": 40,
  "actual_barricades": 65,
  "actual_patrol_jeeps": 4,
  "actual_tow_vehicles": 2,
  "actual_command_vans": 1
}
```

---

## 🗄️ Database Schema

SQLite database at `data/learning.db`.

### `predictions` table
```sql
CREATE TABLE predictions (
    prediction_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at        TEXT NOT NULL,
    event_cause       TEXT,
    event_category    TEXT,
    event_subcategory TEXT,
    corridor          TEXT,
    corridor_norm     TEXT,
    hour              INTEGER,
    day_of_week       INTEGER,
    pred_severity     TEXT,
    pred_confidence   REAL,
    pred_duration     REAL,
    pred_officers     INTEGER,
    pred_barricades   INTEGER,
    pred_patrol_jeeps INTEGER,
    pred_tow_vehicles INTEGER,
    pred_command_vans INTEGER,
    features_json     TEXT
);
```

### `outcomes` table
```sql
CREATE TABLE outcomes (
    outcome_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id       INTEGER NOT NULL REFERENCES predictions(prediction_id),
    recorded_at         TEXT NOT NULL,
    actual_severity     TEXT,
    actual_duration     REAL,
    severity_correct    INTEGER,   -- 1 if severity matched prediction, 0 if not
    duration_error      REAL,      -- |actual - predicted| in minutes
    actual_officers     INTEGER,
    actual_barricades   INTEGER,
    actual_patrol_jeeps INTEGER,
    actual_tow_vehicles INTEGER,
    actual_command_vans INTEGER
);
```

> Both tables support forward-compatible schema migration via `ALTER TABLE ADD COLUMN` inside `try-except` blocks in `_init_db()`.

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.10+
- Node.js 18+
- A Google Gemini API key (optional — system works offline without it)

### 1. Clone the repository
```bash
git clone https://github.com/Shriyagautam12/AegisTraffic.git
cd AegisTraffic
```

### 2. Create a Python virtual environment
```bash
python3 -m venv venv
source venv/bin/activate       # macOS/Linux
# venv\Scripts\activate        # Windows
```

### 3. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

> The system works fully without a Gemini API key — the Copilot falls back to a structured non-LLM response.

### 5. Install frontend dependencies
```bash
cd frontend
npm install
cd ..
```

---

## 🚀 Running the Application

### Development mode (recommended)

**Terminal 1 — Backend (FastAPI):**
```bash
python3 -m uvicorn main:app --port 8000 --reload
```

**Terminal 2 — Frontend (Vite dev server):**
```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

> The Vite dev server proxies `/api/*` requests to the FastAPI backend on port 8000.

### Production mode

Build the frontend and serve everything from FastAPI:
```bash
cd frontend
npm run build
cd ..
python3 -m uvicorn main:app --port 8000
```

Open **http://localhost:8000** in your browser.

---

## 🧪 Training the Models

> Pre-trained models are already included in `models/`. Only run this if you want to retrain from scratch.

```bash
python3 train_models.py
```

This will:
1. Load and clean `data/dataset.xlsx` (8,173 incidents)
2. Perform a strict temporal split (train: Nov–Feb / test: Mar–Apr)
3. Train all 4 LightGBM models with chronological early stopping
4. Save models, encoders, and metadata to `models/`
5. Print full evaluation metrics

Expected output metrics:
```
=== TRIAGE FILTER ===
Accuracy: ~0.90  (auto-triage of minor incidents)

=== BINARY HIGH-IMPACT CLASSIFIER ===
Accuracy: ~0.85  Recall: ~0.80 (catches 80% of all critical events)

=== 3-CLASS SEVERITY CLASSIFIER ===
Accuracy: ~0.78  F1 macro: ~0.72

=== DURATION REGRESSOR ===
MAE: ~28 min  Median AE: ~18 min  R2(log): ~0.65
```

---

## 📁 Project Structure

```
AegisTraffic/
├── main.py                    # FastAPI app — all REST endpoints
├── app_core.py                # Engine singleton initialization (loaded once at startup)
├── train_models.py            # Model training script
├── requirements.txt           # Python dependencies
├── .env                       # Environment variables (GEMINI_API_KEY)
│
├── modules/                   # Core AI/ML engine modules
│   ├── data_pipeline.py       # Data loading, feature engineering, label creation
│   ├── intelligence.py        # Module 1: Historical intelligence engine
│   ├── predictor.py           # Module 2: LightGBM inference engine + SHAP
│   ├── retrieval.py           # Module 3: Cosine similarity event retriever
│   ├── recommender.py         # Module 4: Deterministic resource recommender
│   ├── visualizer.py          # Module 5: Chart/map data generator
│   ├── copilot.py             # Module 6: Gemini RAG copilot
│   └── learning.py            # Module 7: Post-event learning engine
│
├── models/                    # Trained model files (joblib)
│   ├── triage_clf.joblib
│   ├── impact_binary_clf.joblib
│   ├── severity_clf.joblib
│   ├── duration_reg.joblib
│   ├── encoders.joblib
│   └── model_metadata.joblib
│
├── data/
│   ├── dataset.xlsx           # 8,173 historical Bengaluru incident records
│   └── learning.db            # SQLite database (predictions + outcomes)
│
├── utils/
│   └── constants.py           # All path constants, feature lists, hyperparameters
│
├── pages/                     # Legacy Streamlit pages (retained for reference)
│   ├── 1_🗺️_Risk_Intelligence.py
│   ├── 2_event_simulator.py
│   ├── 3_copilot.py
│   └── 4_learning_loop.py
│
└── frontend/                  # React + Vite frontend
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx            # Root component + tab routing
        ├── index.css          # Design system (CSS variables, glassmorphism, animations)
        └── components/
            ├── Header.jsx              # IST clock header
            ├── Sidebar.jsx             # Navigation sidebar
            ├── RiskIntelligence.jsx    # Tab 1: Risk dashboard + maps
            ├── EventSimulator.jsx      # Tab 2: Simulator + feedback form
            ├── AICopilot.jsx           # Tab 3: Natural language interface
            └── LearningLoop.jsx        # Tab 4: Post-event learning dashboard
```

---

## 🔧 Configuration & Environment

### `.env` file
```env
GEMINI_API_KEY=your_key_here
```

### Key constants (`utils/constants.py`)
| Constant | Value | Description |
|---|---|---|
| `TEST_SPLIT_MONTH` | `(2024, 3)` | Temporal train/test cutoff |
| `DURATION_CAP_MINS` | `480` | 8h cap for duration regression target |
| `LEARNING_DB_PATH` | `data/learning.db` | SQLite learning database |
| `MIN_OUTCOMES_FOR_CORRECTION` | `5` | Minimum outcomes before corridor correction is trusted |
| `CORRECTION_MIN / MAX` | `0.5 / 2.0` | Correction factor clamp range |
| `CHRONIC_THRESHOLD_MINS` | `200` | Junction flagged chronic if median closure > this |
| `PEAK_HOURS` | `{4,5,6,7,19,20,21,22}` | Bengaluru morning + evening rush hours |

### Bengaluru Corridors monitored
`Airport New South Road`, `Bannerghatta Road`, `Bellary Road 1`, `Bellary Road 2`, `CBD 1`, `CBD 2`, `Hennur Main Road`, `Hosur Road`, `IRR (Thanisandra Road)`, `Magadi Road`, `Mysore Road`, `Non-corridor`, `Old Airport Road`, `Old Madras Road`, `ORR East 1`, `ORR East 2`, `ORR North 1`, `ORR North 2`, `ORR West 1`, `Tumkur Road`, `Varthur Road`, `West of Chord Road`

---

## 📊 Dataset

- **Source**: Bengaluru City Traffic Police historical incident records
- **Size**: 8,173 incidents
- **Format**: Excel (`.xlsx`)
- **Date range**: Approx. Nov 2023 – Apr 2024
- **Key fields**: `event_cause`, `corridor`, `junction`, `zone`, `police_station`, `severity`, `closure_mins`, `start_datetime`, `requires_road_closure`, `vehicle_type`, `latitude`, `longitude`

---

<p align="center">Built for <strong>Bengaluru City Traffic Police</strong> · AegisTraffic v2.0</p>
