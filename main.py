import math
import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import numpy as np
import sqlite3

from app_core import get_engines
from modules.data_pipeline import PEAK_HOURS
from utils.constants import LEARNING_DB_PATH

app = FastAPI(title="AegisTraffic API", version="1.0")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper to clean pandas values before returning JSON
def clean_val(v):
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: clean_val(val) for k, val in v.items()}
    if isinstance(v, list):
        return [clean_val(val) for val in v]
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(v, np.ndarray):
        return [clean_val(x) for x in v.tolist()]
    return v

def clean_df(df: pd.DataFrame) -> list:
    records = df.to_dict(orient="records")
    return [clean_val(r) for r in records]


# Cache-initialized engine instance
engines = get_engines()
intel = engines["intel"]
predictor = engines["predictor"]
retriever = engines["retriever"]
recommender = engines["recommender"]
copilot = engines["copilot"]
learning = engines["learning"]


# ── Pydantic Request Models ──────────────────────────────────────────────────

class SimulationRequest(BaseModel):
    event_cause: str
    corridor: str
    veh_type: Optional[str] = None
    start_date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    duration_hrs: float
    requires_road_closure: bool

class NarrativeRequest(BaseModel):
    event: dict
    prediction: dict

class ChatRequest(BaseModel):
    query: str

class OutcomeRequest(BaseModel):
    prediction_id: int
    actual_severity: str
    actual_duration: float


# ── REST API Endpoints ───────────────────────────────────────────────────────

@app.get("/api/overview")
def get_overview():
    try:
        stats = intel.get_summary_stats()
        mi = predictor.get_model_info()
        tri_acc = mi.get("triage_metrics", {}).get("accuracy", 0)
        crit_recall = mi.get("binary_metrics", {}).get("recall", 0)
        
        from modules.data_pipeline import get_cause_distribution
        top_corr = intel.get_top_corridors(10)
        cd = get_cause_distribution(engines["df"]).head(8).reset_index()
        cd.columns = ["cause", "count"]
        
        return {
            "total_incidents": stats["total_incidents"],
            "high_severity_pct": stats["high_severity_pct"],
            "planned_events": stats["planned_events"],
            "chronic_junctions": stats["chronic_junctions"],
            "triage_accuracy": round(float(tri_acc) * 100, 1),
            "critical_event_recall": round(float(crit_recall) * 100, 1),
            "corridors_monitored": stats["corridors_monitored"],
            "median_closure_mins": stats["median_closure_mins"],
            "top_corridors": clean_df(top_corr),
            "cause_distribution": clean_df(cd)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/activity-level")
def get_activity_level(hour: Optional[int] = None, day_of_week: Optional[int] = None):
    try:
        now = datetime.datetime.now()
        h = hour if hour is not None else now.hour
        d = day_of_week if day_of_week is not None else now.weekday()
        
        act = intel.get_activity_level(hour=h, day_of_week=d)
        
        # Format time for return
        time_str = now.strftime("%a %H:%M") if (hour is None and day_of_week is None) else f"Selected Time ({h:02d}:00)"
        
        return {
            "hour": h,
            "day_of_week": d,
            "level": act["level"],
            "pct_of_peak": act["pct_of_peak"],
            "peak_hour": act["peak_hour"],
            "time_display": time_str
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/incidents")
def get_incidents():
    try:
        incidents = intel.get_incidents_for_map()
        junctions = intel.get_top_junctions(50)
        chronic = intel.get_chronic_chokepoints()
        
        return {
            "incidents": clean_df(incidents),
            "junctions": clean_df(junctions),
            "chronic": clean_df(chronic)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/simulate")
def run_simulation(req: SimulationRequest):
    try:
        # Parse inputs
        try:
            start_date_parsed = datetime.datetime.strptime(req.start_date, "%Y-%m-%d").date()
            start_time_parsed = datetime.datetime.strptime(req.start_time, "%H:%M").time()
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=f"Invalid date or time format: {ve}")
            
        hour = start_time_parsed.hour
        day_of_week = start_date_parsed.weekday()
        month = start_date_parsed.month
        cause = req.event_cause
        corridor = req.corridor
        veh = req.veh_type
        
        event = {
            "event_cause": cause,
            "corridor": corridor,
            "veh_type": None if veh in ["(none)", None, ""] else veh,
            "day_of_week": day_of_week,
            "hour": hour,
            "month": month,
            "duration_hrs": req.duration_hrs,
            "start_datetime_display": f"{start_date_parsed.strftime('%a %d %b %Y')} {start_time_parsed.strftime('%H:%M')}",
            "is_peak": 1 if hour in PEAK_HOURS else 0,
            "requires_road_closure": req.requires_road_closure,
            "is_planned": 1 if cause in ["public_event", "procession", "vip_movement", "protest", "construction"] else 0,
            "priority": "High" if cause in ["vip_movement", "public_event"] else "Low",
        }
        
        pred = predictor.predict(event)
        
        # Calculate learned corrections
        raw_duration = pred["duration_mins"]
        corrected_duration = learning.apply_correction(corridor, raw_duration)
        cf = learning.get_correction_factor(corridor)
        
        pred["raw_duration_mins"] = raw_duration
        pred["duration_mins"] = corrected_duration
        pred["correction_factor"] = cf
        
        # Resource Recommendation
        rplan = recommender.recommend(event, severity=pred["severity"])
        
        # Similar precedents
        precedents = retriever.summarize_precedent(event, k=5)
        
        # Log prediction
        prediction_id = learning.log_prediction(event, pred)
        
        # Compute diversion plan if closure is required
        from modules.data_pipeline import norm_cat
        dplan = None
        if req.requires_road_closure:
            centroid = recommender._corridor_centroids.get(norm_cat(corridor))
            if centroid:
                origin = (centroid[0] - 0.01, centroid[1] - 0.01)
                dest   = (centroid[0] + 0.01, centroid[1] + 0.01)
                dplan = recommender.diversion_plan(event, origin, dest)
        
        return clean_val({
            "prediction_id": prediction_id,
            "event": event,
            "prediction": pred,
            "resource_plan": rplan,
            "precedents": precedents,
            "diversion_plan": dplan
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/simulate-narrative")
def run_simulation_narrative(req: NarrativeRequest):
    try:
        op = copilot.operational_plan(req.event, prediction=req.prediction)
        return clean_val(op)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/copilot")
def run_copilot(req: ChatRequest):
    try:
        res = copilot.ask(req.query)
        
        # Log prediction if copilot parsed an event successfully
        try:
            ev = res.get("parsed", {})
            ctx = res.get("context", {})
            if ev.get("corridor") and ctx.get("prediction", {}).get("severity"):
                learning.log_prediction(ev, ctx["prediction"])
        except Exception:
            pass
            
        return clean_val({
            "answer": res["answer"],
            "source": res["source"],
            "context": res["context"],
            "parsed": res["parsed"]
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/learning")
def get_learning():
    try:
        report = learning.get_accuracy_report()
        corrections = learning.get_corridor_corrections()
        
        # Fetch open predictions & scatter data
        con = sqlite3.connect(str(LEARNING_DB_PATH))
        preds = pd.read_sql(
            """SELECT prediction_id, corridor, pred_severity, pred_duration FROM predictions
               WHERE prediction_id NOT IN (SELECT prediction_id FROM outcomes)
               ORDER BY prediction_id DESC LIMIT 25""", con)
        scatter = pd.read_sql(
            """SELECT p.pred_duration, o.actual_duration, p.corridor
               FROM outcomes o JOIN predictions p ON o.prediction_id=p.prediction_id
               WHERE p.pred_duration>0 AND o.actual_duration>0""", con)
        con.close()
        
        return clean_val({
            "report": report,
            "corrections": corrections,
            "open_predictions": clean_df(preds),
            "scatter_data": clean_df(scatter)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/learning/outcome")
def record_outcome(req: OutcomeRequest):
    try:
        res = learning.record_outcome(
            req.prediction_id,
            actual_severity=req.actual_severity,
            actual_duration_mins=req.actual_duration
        )
        return clean_val(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Host static build files in production ──────────────────────────────────
# This mounts the 'frontend/dist' directory for serving the compiled React build
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
    
    # Fallback to index.html for React Router SPA paths
    @app.exception_handler(404)
    def custom_404_handler(request, exc):
        return FileResponse(os.path.join(frontend_dist, "index.html"))
