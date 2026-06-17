"""
train_models.py — One-time training script for Module 2.

Trains:
  1. Severity classifier (LightGBM, 3-class)
  2. Duration regressor (LightGBM, log-minutes)

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
    mean_absolute_error, mean_squared_error, r2_score,
)

from modules.data_pipeline import load_data, get_feature_matrix, get_corridor_stats
from utils.constants import (
    SEVERITY_MODEL_PATH, DURATION_MODEL_PATH, ENCODERS_PATH, METADATA_PATH,
    FEATURE_COLS, SEVERITY_TO_INT, DURATION_CAP_MINS, TEST_SPLIT_MONTH,
    MODELS_DIR,
)


def build_encoders(df: pd.DataFrame) -> dict:
    """
    Build value->code mappings for each categorical, so inference can encode
    new events identically to training.

    Encoding is done on the SAME column used in load_data():
      - event_cause: already normalized in place
      - corridor/zone/veh_type: their _norm helper column
    Keys are normalized (lowercased) so inference lookups are case-insensitive.
    """
    encoders = {}
    # event_cause is normalized in place by load_data
    cats = df["event_cause"].astype("category").cat.categories
    encoders["event_cause"] = {cat: i for i, cat in enumerate(cats)}
    # others use the _norm helper column
    for col in ["corridor", "zone", "veh_type"]:
        cats = df[f"{col}_norm"].astype("category").cat.categories
        encoders[col] = {cat: i for i, cat in enumerate(cats)}
    return encoders


def temporal_split(fm: pd.DataFrame):
    """Split on month: Nov2023-Feb2024 = train, Mar-Apr2024 = test."""
    split_year, split_month = TEST_SPLIT_MONTH
    cutoff = pd.Timestamp(year=split_year, month=split_month, day=1, tz="UTC")
    train = fm[fm["start_datetime"] < cutoff].copy()
    test  = fm[fm["start_datetime"] >= cutoff].copy()
    return train, test


def train_severity(train, test):
    """Train the 3-class severity classifier."""
    X_train = train[FEATURE_COLS]
    y_train = train["severity"].map(SEVERITY_TO_INT)
    X_test  = test[FEATURE_COLS]
    y_test  = test["severity"].map(SEVERITY_TO_INT)

    model = lgb.LGBMClassifier(
        objective="multiclass",
        num_class=3,
        n_estimators=400,
        learning_rate=0.05,
        num_leaves=31,
        max_depth=-1,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    metrics = {
        "accuracy":  round(float(accuracy_score(y_test, preds)), 4),
        "f1_macro":  round(float(f1_score(y_test, preds, average="macro")), 4),
        "f1_weighted": round(float(f1_score(y_test, preds, average="weighted")), 4),
        "n_test":    int(len(y_test)),
    }
    print("\n=== SEVERITY CLASSIFIER ===")
    print(f"Train rows: {len(X_train)} | Test rows: {len(X_test)}")
    print(f"Accuracy:  {metrics['accuracy']}")
    print(f"F1 macro:  {metrics['f1_macro']}")
    print(f"F1 weighted: {metrics['f1_weighted']}")
    print("\nClassification report:")
    print(classification_report(y_test, preds,
          target_names=["Low", "Medium", "High"], zero_division=0))
    print("Confusion matrix (rows=true, cols=pred):")
    print(confusion_matrix(y_test, preds))

    return model, metrics


def train_duration(train, test):
    """Train the duration regressor on rows with valid closure_mins."""
    tr = train.dropna(subset=["closure_mins"]).copy()
    te = test.dropna(subset=["closure_mins"]).copy()

    # Cap extreme durations so the model learns response time, not chronic issues
    tr["closure_capped"] = tr["closure_mins"].clip(upper=DURATION_CAP_MINS)
    te["closure_capped"] = te["closure_mins"].clip(upper=DURATION_CAP_MINS)
    tr["log_target"] = np.log1p(tr["closure_capped"])
    te["log_target"] = np.log1p(te["closure_capped"])

    X_train, y_train = tr[FEATURE_COLS], tr["log_target"]
    X_test,  y_test  = te[FEATURE_COLS], te["log_target"]

    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=400,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )
    model.fit(X_train, y_train)

    log_preds = model.predict(X_test)
    # Residual std in log space (for prediction intervals)
    resid_std = float(np.std(y_test - log_preds))

    # Metrics in real minutes
    pred_mins = np.expm1(log_preds)
    true_mins = te["closure_capped"].values
    metrics = {
        "mae_mins":  round(float(mean_absolute_error(true_mins, pred_mins)), 1),
        "rmse_mins": round(float(np.sqrt(mean_squared_error(true_mins, pred_mins))), 1),
        "r2_log":    round(float(r2_score(y_test, log_preds)), 4),
        "median_ae_mins": round(float(np.median(np.abs(true_mins - pred_mins))), 1),
        "n_test":    int(len(y_test)),
        "resid_std": round(resid_std, 4),
    }
    print("\n=== DURATION REGRESSOR ===")
    print(f"Train rows: {len(X_train)} | Test rows: {len(X_test)}")
    print(f"MAE:        {metrics['mae_mins']} min")
    print(f"Median AE:  {metrics['median_ae_mins']} min")
    print(f"RMSE:       {metrics['rmse_mins']} min")
    print(f"R2 (log):   {metrics['r2_log']}")

    return model, metrics, resid_std


def main():
    MODELS_DIR.mkdir(exist_ok=True)
    print("Loading data...")
    df = load_data()
    fm = get_feature_matrix(df)
    print(f"Feature matrix: {fm.shape}")

    encoders = build_encoders(df)
    corridor_stats = get_corridor_stats(df)
    corridor_risk_lookup = dict(
        zip(corridor_stats["corridor"], corridor_stats["corridor_risk_index"])
    )

    train, test = temporal_split(fm)

    sev_model, sev_metrics = train_severity(train, test)
    dur_model, dur_metrics, resid_std = train_duration(train, test)

    metadata = {
        "trained_at":           datetime.now(timezone.utc).isoformat(),
        "model_version":        "1.0",
        "n_train":              int(len(train)),
        "n_test":               int(len(test)),
        "feature_cols":         FEATURE_COLS,
        "severity_metrics":     sev_metrics,
        "duration_metrics":     dur_metrics,
        "duration_resid_std":   resid_std,
        "corridor_risk_lookup": corridor_risk_lookup,
    }

    print("\nSaving models...")
    joblib.dump(sev_model, SEVERITY_MODEL_PATH)
    joblib.dump(dur_model, DURATION_MODEL_PATH)
    joblib.dump(encoders,  ENCODERS_PATH)
    joblib.dump(metadata,  METADATA_PATH)
    print(f"Saved to {MODELS_DIR}/")
    print("\nDone.")


if __name__ == "__main__":
    main()
