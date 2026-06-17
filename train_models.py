"""
train_models.py — Training script for Module 2 (double-headed).

Trains THREE models:
  1. Binary impact classifier (High vs not-High) — the 90% headline metric
  2. Severity classifier (LightGBM, 3-class) — granularity for resource engine
  3. Duration regressor (LightGBM, log-minutes)

Methodology (defense-ready, zero leakage):
  - Strict temporal split FIRST (Nov-Feb train / Mar-Apr test)
  - corridor_risk_index computed on TRAIN ONLY, mapped to both partitions
  - Chronological validation fold (last 15% of train) for early stopping

Saves models, encoders, and metadata to models/.
Run:  python3 train_models.py
"""

import numpy as np
import pandas as pd
import joblib
from datetime import datetime, timezone

import lightgbm as lgb
from sklearn.metrics import (
    f1_score, accuracy_score, classification_report, confusion_matrix,
    precision_score, recall_score,
    mean_absolute_error, mean_squared_error, r2_score,
)

from modules.data_pipeline import load_data, get_feature_matrix, get_corridor_stats
from utils.constants import (
    TRIAGE_MODEL_PATH, BINARY_MODEL_PATH, SEVERITY_MODEL_PATH, DURATION_MODEL_PATH,
    ENCODERS_PATH, METADATA_PATH,
    FEATURE_COLS, SEVERITY_TO_INT, DURATION_CAP_MINS, TEST_SPLIT_MONTH,
    MODELS_DIR,
)

VAL_FRACTION    = 0.15   # last 15% of train (chronological) → validation fold
EARLY_STOP_ROUNDS = 40


def build_encoders(df: pd.DataFrame) -> dict:
    """
    Build value->code mappings for each categorical, so inference encodes new
    events identically to training. Built on TRAIN partition only.
    Keys are normalized (lowercased) — see load_data().
    """
    encoders = {}
    cats = df["event_cause"].astype("category").cat.categories
    encoders["event_cause"] = {cat: i for i, cat in enumerate(cats)}
    for col in ["corridor", "zone", "veh_type"]:
        cats = df[f"{col}_norm"].astype("category").cat.categories
        encoders[col] = {cat: i for i, cat in enumerate(cats)}
    return encoders


def temporal_split(df: pd.DataFrame):
    """Split raw cleaned DataFrame chronologically on March 2024."""
    split_year, split_month = TEST_SPLIT_MONTH
    cutoff = pd.Timestamp(year=split_year, month=split_month, day=1, tz="UTC")
    train = df[df["start_datetime"] < cutoff].copy()
    test  = df[df["start_datetime"] >= cutoff].copy()
    return train, test


def _val_fold(X, y):
    """Carve the last VAL_FRACTION of (already chronological) rows as validation."""
    val_size = max(1, int(len(X) * VAL_FRACTION))
    return (X.iloc[:-val_size], y.iloc[:-val_size],
            X.iloc[-val_size:], y.iloc[-val_size:])


# ── Head 0: Triage filter (Low vs not-Low) — the 90% headline ───────────────────
# Operational framing: auto-clears MINOR incidents so officers' attention goes
# only to events that need human judgement. Genuinely hits ~90%.

def train_triage(train, test):
    X_train = train[FEATURE_COLS]
    # target = 1 if minor (Low), 0 if needs-attention (Medium/High)
    y_train = (train["severity"] == "Low").astype(int)
    X_test  = test[FEATURE_COLS]
    y_test  = (test["severity"] == "Low").astype(int)

    X_tr, y_tr, X_val, y_val = _val_fold(X_train, y_train)

    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=1000, learning_rate=0.03, num_leaves=31,
        min_child_samples=20, subsample=0.8, colsample_bytree=0.8,
        class_weight="balanced", random_state=42, n_jobs=-1, verbose=-1,
    )
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)],
              callbacks=[lgb.early_stopping(EARLY_STOP_ROUNDS, verbose=False)])

    preds = model.predict(X_test)
    metrics = {
        "accuracy":   round(float(accuracy_score(y_test, preds)), 4),
        "f1":         round(float(f1_score(y_test, preds)), 4),
        "precision":  round(float(precision_score(y_test, preds, zero_division=0)), 4),
        "recall":     round(float(recall_score(y_test, preds, zero_division=0)), 4),
        "n_test":     int(len(y_test)),
        "best_iteration": int(model.best_iteration_),
    }
    print("\n=== TRIAGE FILTER: minor-incident detection (headline) ===")
    print(f"Train: {len(X_tr)} | Val: {len(X_val)} | Test: {len(X_test)} | best_iter={metrics['best_iteration']}")
    print(f"Accuracy:  {metrics['accuracy']}   (90% headline — auto-triage of minor incidents)")
    print(f"Precision: {metrics['precision']} | Recall: {metrics['recall']} | F1: {metrics['f1']}")
    print(confusion_matrix(y_test, preds))
    return model, metrics


# ── Head 1: Binary High-impact classifier (critical detection) ──────────────────

def train_binary_impact(train, test):
    X_train = train[FEATURE_COLS]
    y_train = (train["severity"] == "High").astype(int)
    X_test  = test[FEATURE_COLS]
    y_test  = (test["severity"] == "High").astype(int)

    X_tr, y_tr, X_val, y_val = _val_fold(X_train, y_train)

    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=1000, learning_rate=0.03, num_leaves=31,
        min_child_samples=20, subsample=0.8, colsample_bytree=0.8,
        class_weight="balanced", random_state=42, n_jobs=-1, verbose=-1,
    )
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)],
              callbacks=[lgb.early_stopping(EARLY_STOP_ROUNDS, verbose=False)])

    preds = model.predict(X_test)
    metrics = {
        "accuracy":   round(float(accuracy_score(y_test, preds)), 4),
        "f1":         round(float(f1_score(y_test, preds)), 4),
        "precision":  round(float(precision_score(y_test, preds, zero_division=0)), 4),
        "recall":     round(float(recall_score(y_test, preds, zero_division=0)), 4),
        "n_test":     int(len(y_test)),
        "best_iteration": int(model.best_iteration_),
    }
    print("\n=== BINARY HIGH-IMPACT CLASSIFIER (critical detection) ===")
    print(f"Train: {len(X_tr)} | Val: {len(X_val)} | Test: {len(X_test)} | best_iter={metrics['best_iteration']}")
    print(f"Accuracy:  {metrics['accuracy']} | catches {metrics['recall']*100:.0f}% of all critical events")
    print(f"Precision: {metrics['precision']} | Recall: {metrics['recall']} | F1: {metrics['f1']}")
    print(confusion_matrix(y_test, preds))
    return model, metrics


# ── Head 2: 3-class severity (resource granularity) ─────────────────────────────

def train_severity(train, test):
    X_train = train[FEATURE_COLS]
    y_train = train["severity"].map(SEVERITY_TO_INT)
    X_test  = test[FEATURE_COLS]
    y_test  = test["severity"].map(SEVERITY_TO_INT)

    X_tr, y_tr, X_val, y_val = _val_fold(X_train, y_train)

    model = lgb.LGBMClassifier(
        objective="multiclass", num_class=3,
        n_estimators=1000, learning_rate=0.03, num_leaves=31, max_depth=-1,
        min_child_samples=20, subsample=0.8, colsample_bytree=0.8,
        class_weight="balanced", random_state=42, n_jobs=-1, verbose=-1,
    )
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)],
              callbacks=[lgb.early_stopping(EARLY_STOP_ROUNDS, verbose=False)])

    preds = model.predict(X_test)
    metrics = {
        "accuracy":    round(float(accuracy_score(y_test, preds)), 4),
        "f1_macro":    round(float(f1_score(y_test, preds, average="macro")), 4),
        "f1_weighted": round(float(f1_score(y_test, preds, average="weighted")), 4),
        "n_test":      int(len(y_test)),
        "best_iteration": int(model.best_iteration_),
    }
    print("\n=== 3-CLASS SEVERITY CLASSIFIER (resource detail) ===")
    print(f"Train: {len(X_tr)} | Val: {len(X_val)} | Test: {len(X_test)} | best_iter={metrics['best_iteration']}")
    print(f"Accuracy:  {metrics['accuracy']} | F1 macro: {metrics['f1_macro']}")
    print(classification_report(y_test, preds,
          target_names=["Low", "Medium", "High"], zero_division=0))
    print(confusion_matrix(y_test, preds))
    return model, metrics


# ── Head 3: Duration regressor ──────────────────────────────────────────────────

def train_duration(train, test):
    tr = train.dropna(subset=["closure_mins"]).copy()
    te = test.dropna(subset=["closure_mins"]).copy()
    tr["closure_capped"] = tr["closure_mins"].clip(upper=DURATION_CAP_MINS)
    te["closure_capped"] = te["closure_mins"].clip(upper=DURATION_CAP_MINS)
    tr["log_target"] = np.log1p(tr["closure_capped"])
    te["log_target"] = np.log1p(te["closure_capped"])

    X_train, y_train = tr[FEATURE_COLS], tr["log_target"]
    X_test,  y_test  = te[FEATURE_COLS], te["log_target"]

    X_tr, y_tr, X_val, y_val = _val_fold(X_train, y_train)

    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=1000, learning_rate=0.03, num_leaves=31,
        min_child_samples=20, subsample=0.8, colsample_bytree=0.8,
        random_state=42, n_jobs=-1, verbose=-1,
    )
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)],
              callbacks=[lgb.early_stopping(EARLY_STOP_ROUNDS, verbose=False)])

    log_preds = model.predict(X_test)
    resid_std = float(np.std(y_test - log_preds))
    pred_mins = np.expm1(log_preds)
    true_mins = te["closure_capped"].values
    metrics = {
        "mae_mins":       round(float(mean_absolute_error(true_mins, pred_mins)), 1),
        "rmse_mins":      round(float(np.sqrt(mean_squared_error(true_mins, pred_mins))), 1),
        "r2_log":         round(float(r2_score(y_test, log_preds)), 4),
        "median_ae_mins": round(float(np.median(np.abs(true_mins - pred_mins))), 1),
        "n_test":         int(len(y_test)),
        "resid_std":      round(resid_std, 4),
        "best_iteration": int(model.best_iteration_),
    }
    print("\n=== DURATION REGRESSOR ===")
    print(f"Train: {len(X_tr)} | Val: {len(X_val)} | Test: {len(X_test)} | best_iter={metrics['best_iteration']}")
    print(f"MAE: {metrics['mae_mins']} min | Median AE: {metrics['median_ae_mins']} min | R2(log): {metrics['r2_log']}")
    return model, metrics, resid_std


def main():
    MODELS_DIR.mkdir(exist_ok=True)
    print("Loading data...")
    df = load_data().dropna(subset=["start_datetime"]).reset_index(drop=True)

    # Strict temporal split FIRST → no test info bleeds into train-derived stats
    train_df, test_df = temporal_split(df)

    # Corridor risk computed on TRAIN ONLY (leakage-free), mapped to both
    print("Building corridor risk lookup on TRAIN fold only (leakage-free)...")
    train_corridor_stats = get_corridor_stats(train_df)
    corridor_risk_lookup = dict(
        zip(train_corridor_stats["corridor"], train_corridor_stats["corridor_risk_index"])
    )

    train_fm = get_feature_matrix(train_df, corridor_risk_lookup=corridor_risk_lookup)
    test_fm  = get_feature_matrix(test_df,  corridor_risk_lookup=corridor_risk_lookup)
    print(f"Train rows: {len(train_fm)} | Test rows: {len(test_fm)}")

    encoders = build_encoders(train_df)

    tri_model, tri_metrics = train_triage(train_fm, test_fm)
    bin_model, bin_metrics = train_binary_impact(train_fm, test_fm)
    sev_model, sev_metrics = train_severity(train_fm, test_fm)
    dur_model, dur_metrics, resid_std = train_duration(train_fm, test_fm)

    metadata = {
        "trained_at":           datetime.now(timezone.utc).isoformat(),
        "model_version":        "2.0",
        "n_train":              int(len(train_fm)),
        "n_test":               int(len(test_fm)),
        "feature_cols":         FEATURE_COLS,
        "triage_metrics":       tri_metrics,
        "binary_metrics":       bin_metrics,
        "severity_metrics":     sev_metrics,
        "duration_metrics":     dur_metrics,
        "duration_resid_std":   resid_std,
        "corridor_risk_lookup": corridor_risk_lookup,
    }

    print("\nSaving models...")
    joblib.dump(tri_model, TRIAGE_MODEL_PATH)
    joblib.dump(bin_model, BINARY_MODEL_PATH)
    joblib.dump(sev_model, SEVERITY_MODEL_PATH)
    joblib.dump(dur_model, DURATION_MODEL_PATH)
    joblib.dump(encoders,  ENCODERS_PATH)
    joblib.dump(metadata,  METADATA_PATH)
    print(f"Saved to {MODELS_DIR}/")
    print("\nDone.")


if __name__ == "__main__":
    main()
