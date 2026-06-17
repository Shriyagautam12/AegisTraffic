"""
Data Pipeline — AegisTraffic
Loads raw dataset, cleans, engineers features, creates labels.
All downstream modules import load_data() from here.
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "dataset.xlsx"


def norm_cat(value):
    """
    Normalize a categorical string: strip whitespace + lowercase.
    Makes all category matching case-insensitive and whitespace-robust.
    Returns None for null/NaN so downstream .map() yields NaN cleanly.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value).strip().lower()

# ── Severity thresholds ────────────────────────────────────────────────────────
HIGH_CLOSURE_MINS   = 120   # > 2 hours → High
MEDIUM_CLOSURE_MINS = 40    # 40–120 min → Medium

# ── Peak hour windows (Bengaluru-specific based on EDA) ───────────────────────
MORNING_PEAK = {4, 5, 6, 7}
EVENING_PEAK = {19, 20, 21, 22}
PEAK_HOURS   = MORNING_PEAK | EVENING_PEAK

# ── Corridor risk tier (derived from EDA: median closure time) ────────────────
# Tier 1 = highest risk corridors (median closure > 100 min)
CORRIDOR_RISK_TIER = {
    "CBD 2":                    3,
    "Hennur Main Road":         3,
    "Airport New South Road":   3,
    "ORR East 1":               2,
    "Non-corridor":             2,
    "ORR West 1":               2,
    "Hosur Road":               2,
    "ORR North 1":              2,
    "Bannerghatta Road":        2,
    "Old Airport Road":         2,
    "Mysore Road":              2,
    "Bellary Road 1":           1,
    "Bellary Road 2":           1,
    "Tumkur Road":              1,
    "Magadi Road":              1,
    "ORR North 2":              1,
    "Old Madras Road":          1,
    "West of Chord Road":       1,
    "ORR East 2":               1,
    "Varthur Road":             1,
    "IRR(Thanisandra road)":    1,
    "CBD 1":                    2,
}

# ── Event cause severity mapping (derived from EDA: High% per cause) ──────────
CAUSE_SEVERITY_SCORE = {
    "vip_movement":      5,
    "debris":            5,
    "Debris":            5,
    "road_conditions":   4,
    "tree_fall":         4,
    "water_logging":     3,
    "public_event":      3,
    "construction":      3,
    "protest":           3,
    "pot_holes":         2,
    "procession":        2,
    "congestion":        2,
    "others":            2,
    "vehicle_breakdown": 1,
    "accident":          1,
    "Fog / Low Visibility": 2,
    "test_demo":         0,
}

# ── Vehicle type risk score ────────────────────────────────────────────────────
VEH_RISK_SCORE = {
    "heavy_vehicle": 4,
    "truck":         4,
    "bmtc_bus":      3,
    "ksrtc_bus":     3,
    "private_bus":   2,
    "lcv":           2,
    "taxi":          1,
    "private_car":   1,
    "auto":          1,
    "others":        1,
}

# ── Case-insensitive lookup variants (keyed by norm_cat output) ───────────────
# These are the dicts actually used at runtime. norm_cat() lowercases + strips,
# so every key here is lowercased to guarantee case-insensitive matching.
CAUSE_SEVERITY_SCORE_NORM = {norm_cat(k): v for k, v in CAUSE_SEVERITY_SCORE.items()}
CORRIDOR_RISK_TIER_NORM   = {norm_cat(k): v for k, v in CORRIDOR_RISK_TIER.items()}
VEH_RISK_SCORE_NORM       = {norm_cat(k): v for k, v in VEH_RISK_SCORE.items()}


def _assign_severity(row: pd.Series) -> str:
    """Derive severity label from available fields."""
    closure = row.get("closure_mins", np.nan)
    if row["requires_road_closure"] is True:
        return "High"
    if pd.notna(closure) and closure > HIGH_CLOSURE_MINS:
        return "High"
    if row["priority"] == "High" or (pd.notna(closure) and closure > MEDIUM_CLOSURE_MINS):
        return "Medium"
    return "Low"


def load_data(path: Path = DATA_PATH) -> pd.DataFrame:
    """
    Load and clean the raw Excel dataset.
    Returns a DataFrame ready for EDA and feature engineering.
    """
    df = pd.read_excel(path)

    # ── Timestamps ────────────────────────────────────────────────────────────
    for col in ["start_datetime", "end_datetime", "closed_datetime",
                "resolved_datetime", "created_date", "modified_datetime"]:
        df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    # ── Duration targets ──────────────────────────────────────────────────────
    df["closure_mins"] = (
        (df["closed_datetime"] - df["start_datetime"])
        .dt.total_seconds() / 60
    )
    # Negative or zero closures are data errors — nullify them
    df.loc[df["closure_mins"] <= 0, "closure_mins"] = np.nan

    # Planned event duration (only valid for planned events with end_datetime)
    df["planned_duration_hrs"] = np.where(
        df["event_type"] == "planned",
        (df["end_datetime"] - df["start_datetime"]).dt.total_seconds() / 3600,
        0.0,
    )
    df["planned_duration_hrs"] = df["planned_duration_hrs"].clip(lower=0)

    # ── Temporal features ─────────────────────────────────────────────────────
    df["hour"]        = df["start_datetime"].dt.hour
    df["day_of_week"] = df["start_datetime"].dt.dayofweek   # 0=Mon, 6=Sun
    df["month"]       = df["start_datetime"].dt.month
    df["day_name"]    = df["start_datetime"].dt.day_name()
    df["is_peak"]     = df["hour"].isin(PEAK_HOURS).astype(int)
    df["is_weekend"]  = (df["day_of_week"] >= 5).astype(int)
    df["is_planned"]  = (df["event_type"] == "planned").astype(int)

    # ── Severity label ────────────────────────────────────────────────────────
    df["severity"] = df.apply(_assign_severity, axis=1)

    # ── Normalize categoricals FIRST (case-insensitive, whitespace-robust) ────
    # event_cause is fully normalized (lowercased) because it has known casing
    # dupes (Debris/debris) and is only ever used as a code/key, never displayed
    # as a proper noun. corridor/zone/veh_type keep their original display case
    # but get a hidden _norm helper column used for all matching/encoding.
    df["event_cause"] = df["event_cause"].map(norm_cat)
    df["event_cause"] = df["event_cause"].replace(
        {"fog / low visibility": "fog_low_visibility"}
    )

    for col in ["corridor", "zone", "veh_type", "police_station", "event_type"]:
        df[f"{col}_norm"] = df[col].map(norm_cat)

    # ── Scored features (use normalized lookup dicts → case-insensitive) ──────
    df["cause_score"]      = df["event_cause"].map(CAUSE_SEVERITY_SCORE_NORM).fillna(1)
    df["corridor_tier"]    = df["corridor_norm"].map(CORRIDOR_RISK_TIER_NORM).fillna(1)
    df["veh_risk"]         = df["veh_type_norm"].map(VEH_RISK_SCORE_NORM).fillna(1)
    df["priority_num"]     = (df["priority"] == "High").astype(int)
    df["road_closure_num"] = df["requires_road_closure"].astype(int)

    # ── Label-encode on normalized values (codes now case-consistent) ─────────
    # event_cause is already normalized; others use their _norm helper column.
    df["event_cause_enc"] = df["event_cause"].astype("category").cat.codes
    for col in ["corridor", "zone", "veh_type", "police_station", "event_type"]:
        df[f"{col}_enc"] = df[f"{col}_norm"].astype("category").cat.codes

    # ── Log-transformed duration (for regression) ─────────────────────────────
    df["log_closure_mins"] = np.log1p(df["closure_mins"])

    return df


def get_feature_matrix(df: pd.DataFrame, corridor_risk_lookup: dict = None) -> pd.DataFrame:
    """
    Return the ML-ready feature matrix.
    Rows with no start_datetime are dropped.
    Injects corridor_risk_index (from get_corridor_stats) as a feature so the
    ML model sees each corridor's historical risk, not just its label code.

    To eliminate target leakage, pass corridor_risk_lookup computed strictly on
    the training partition. If None, it's computed on the incoming df (legacy).
    """
    feature_cols = [
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
        "corridor_risk_index",
        "event_cause_enc",
        "corridor_enc",
        "zone_enc",
        "veh_type_enc",
    ]
    df_feat = df.dropna(subset=["start_datetime"]).copy()

    # Inject corridor_risk_index via lookup from corridor stats.
    # Leakage prevention: use train-only lookup if provided.
    if corridor_risk_lookup is None:
        corridor_stats = get_corridor_stats(df)
        corridor_risk_lookup = dict(
            zip(corridor_stats["corridor"], corridor_stats["corridor_risk_index"])
        )
    df_feat["corridor_risk_index"] = (
        df_feat["corridor"].map(corridor_risk_lookup).fillna(0.3)
    )

    keep_cols = feature_cols + [
        "severity", "closure_mins", "log_closure_mins", "id", "start_datetime"
    ]
    return df_feat[keep_cols].reset_index(drop=True)


def get_severity_counts(df: pd.DataFrame) -> dict:
    return df["severity"].value_counts().to_dict()


def get_cause_distribution(df: pd.DataFrame) -> pd.Series:
    return df["event_cause"].value_counts()


def get_corridor_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Per-corridor aggregated stats used by Module 1 and Module 4. Excludes Non-corridor."""
    stats = (
        df[df["corridor"] != "Non-corridor"].groupby("corridor")
        .agg(
            incident_count=("id", "count"),
            high_severity_count=("severity", lambda x: (x == "High").sum()),
            road_closure_count=("requires_road_closure", "sum"),
            median_closure_mins=("closure_mins", "median"),
            mean_closure_mins=("closure_mins", "mean"),
        )
        .reset_index()
    )
    stats["high_severity_rate"] = stats["high_severity_count"] / stats["incident_count"]
    stats["road_closure_rate"]  = stats["road_closure_count"]  / stats["incident_count"]
    # Composite risk index 0–1
    for col in ["incident_count", "high_severity_rate", "road_closure_rate"]:
        col_min, col_max = stats[col].min(), stats[col].max()
        denom = col_max - col_min if col_max != col_min else 1
        stats[f"{col}_norm"] = (stats[col] - col_min) / denom
    stats["corridor_risk_index"] = (
        0.4 * stats["incident_count_norm"]
        + 0.4 * stats["high_severity_rate_norm"]
        + 0.2 * stats["road_closure_rate_norm"]
    ).round(4)
    return stats.sort_values("corridor_risk_index", ascending=False)


def get_junction_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Per-junction stats for hotspot detection. Min 3 incidents to be ranked."""
    jdf = df[df["junction"].notna() & (df["junction"] != "")].copy()
    stats = (
        jdf.groupby("junction")
        .agg(
            incident_count=("id", "count"),
            high_count=("severity", lambda x: (x == "High").sum()),
            road_closure_count=("requires_road_closure", "sum"),
            median_closure_mins=("closure_mins", "median"),
            lat=("latitude", "mean"),
            lon=("longitude", "mean"),
        )
        .reset_index()
    )
    # Require at least 3 incidents to appear in hotspot rankings
    stats = stats[stats["incident_count"] >= 3].copy()
    stats["high_rate"] = stats["high_count"] / stats["incident_count"]
    stats["closure_rate"] = stats["road_closure_count"] / stats["incident_count"]
    for col in ["incident_count", "high_rate", "closure_rate"]:
        col_min, col_max = stats[col].min(), stats[col].max()
        denom = col_max - col_min if col_max != col_min else 1
        stats[f"{col}_norm"] = (stats[col] - col_min) / denom
    stats["hotspot_score"] = (
        0.4 * stats["incident_count_norm"]
        + 0.4 * stats["high_rate_norm"]
        + 0.2 * stats["closure_rate_norm"]
    ).round(4)
    return stats.sort_values("hotspot_score", ascending=False)


def get_temporal_risk_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a (24 x 7) matrix: rows=hour, cols=day_of_week.
    Values = incident count — used for 'risk right now' heatmap.
    """
    df_valid = df.dropna(subset=["hour", "day_of_week"])
    matrix = (
        df_valid.groupby(["hour", "day_of_week"])["id"]
        .count()
        .unstack(fill_value=0)
    )
    # Normalise to 0–1
    matrix_norm = (matrix - matrix.min().min()) / (matrix.max().max() - matrix.min().min())
    return matrix_norm
