"""
Shared constants for AegisTraffic.
Keeps feature definitions consistent between training and inference.
"""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT_DIR    = Path(__file__).parent.parent
MODELS_DIR  = ROOT_DIR / "models"
DATA_DIR    = ROOT_DIR / "data"

TRIAGE_MODEL_PATH   = MODELS_DIR / "triage_clf.joblib"          # Low vs not-Low (90% triage filter)
BINARY_MODEL_PATH   = MODELS_DIR / "impact_binary_clf.joblib"   # High vs not-High (critical detection)
SEVERITY_MODEL_PATH = MODELS_DIR / "severity_clf.joblib"        # 3-class (resource detail)
DURATION_MODEL_PATH = MODELS_DIR / "duration_reg.joblib"
ENCODERS_PATH       = MODELS_DIR / "encoders.joblib"
METADATA_PATH       = MODELS_DIR / "model_metadata.joblib"

# ── ML feature set (must match data_pipeline.get_feature_matrix) ───────────────
FEATURE_COLS = [
    "cause_score",
    "corridor_tier",
    "veh_risk",
    "priority_num",
    "road_closure_num",
    "hour",
    "day_of_week",
    "month",
    "is_peak",
    "is_weekend",
    "is_planned",
    "planned_duration_hrs",
    "corridor_risk_index",   # injected from Module 1 at feature-build time
    "event_cause_enc",
    "corridor_enc",
    "zone_enc",
    "veh_type_enc",
]

# Human-readable names for SHAP explanation display
FEATURE_DISPLAY_NAMES = {
    "cause_score":          "Event cause severity",
    "corridor_tier":        "Corridor risk tier",
    "veh_risk":             "Vehicle type risk",
    "priority_num":         "Priority flag",
    "road_closure_num":     "Road closure required",
    "hour":                 "Hour of day",
    "day_of_week":          "Day of week",
    "month":                "Month",
    "is_peak":              "Peak hour",
    "is_weekend":           "Weekend",
    "is_planned":           "Planned event",
    "planned_duration_hrs": "Planned duration",
    "corridor_risk_index":  "Corridor historical risk",
    "event_cause_enc":      "Event cause",
    "corridor_enc":         "Corridor",
    "zone_enc":             "Zone",
    "veh_type_enc":         "Vehicle type",
}

# ── Severity classes ───────────────────────────────────────────────────────────
SEVERITY_CLASSES = ["Low", "Medium", "High"]
SEVERITY_TO_INT  = {"Low": 0, "Medium": 1, "High": 2}
INT_TO_SEVERITY  = {0: "Low", 1: "Medium", 2: "High"}

# ── Duration regressor cap (minutes) ──────────────────────────────────────────
# Closures longer than this are chronic infrastructure issues, not incident
# response time. We cap during training so the regressor learns operational
# response times, not multi-day construction.
DURATION_CAP_MINS = 1440   # 24 hours

# ── Train/test temporal split ─────────────────────────────────────────────────
# Train on Nov 2023 - Feb 2024, test on Mar - Apr 2024
TEST_SPLIT_MONTH = (2024, 3)   # incidents from March 2024 onward are test
