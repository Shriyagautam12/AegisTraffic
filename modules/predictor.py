"""
Module 2 — Operational Impact Predictor
Loads trained LightGBM models and predicts severity + closure duration
for any event, with SHAP-based explanations.

Training lives in train_models.py. This module is inference-only.
"""

import numpy as np
import pandas as pd
import joblib

from utils.constants import (
    SEVERITY_MODEL_PATH, DURATION_MODEL_PATH, ENCODERS_PATH, METADATA_PATH,
    FEATURE_COLS, FEATURE_DISPLAY_NAMES, INT_TO_SEVERITY,
)
from modules.data_pipeline import (
    CAUSE_SEVERITY_SCORE_NORM, CORRIDOR_RISK_TIER_NORM, VEH_RISK_SCORE_NORM,
    PEAK_HOURS, norm_cat,
)


class ImpactPredictor:
    """
    Inference engine. Instantiate once (loads models from disk), then call
    .predict(event_dict) repeatedly.
    """

    def __init__(self):
        self.severity_model = joblib.load(SEVERITY_MODEL_PATH)
        self.duration_model = joblib.load(DURATION_MODEL_PATH)
        self.encoders       = joblib.load(ENCODERS_PATH)
        self.metadata       = joblib.load(METADATA_PATH)

        # Lazy SHAP explainers (built on first use — they're slow to init)
        self._severity_explainer = None
        self._duration_explainer = None

    # ── Feature construction from a raw event dict ──────────────────────────────

    def _encode(self, encoder_name: str, value):
        """
        Map a category value to its integer code using the saved encoder.
        Value is normalized (lowercase/strip) so matching is case-insensitive.
        """
        mapping = self.encoders.get(encoder_name, {})
        return mapping.get(norm_cat(value), -1)   # -1 = unseen category

    def build_features(self, event: dict) -> pd.DataFrame:
        """
        Convert a raw event dict into a single-row feature DataFrame.

        Expected event keys (all optional, sensible defaults applied):
          event_cause, corridor, zone, veh_type, priority,
          requires_road_closure, hour, day_of_week, month,
          is_planned, planned_duration_hrs
        """
        cause    = norm_cat(event.get("event_cause")) or "others"
        corridor = event.get("corridor") or "Non-corridor"
        zone     = event.get("zone")
        veh_type = norm_cat(event.get("veh_type")) or "others"
        hour     = int(event.get("hour", 12))
        dow      = int(event.get("day_of_week", 0))
        month    = int(event.get("month", 1))
        is_planned = int(event.get("is_planned", 0))
        planned_dur = float(event.get("planned_duration_hrs", 0) or 0)
        priority_high = 1 if event.get("priority") == "High" else 0
        road_closure = 1 if event.get("requires_road_closure") else 0

        # Scored features (domain knowledge from EDA) — case-insensitive lookups
        cause_score   = CAUSE_SEVERITY_SCORE_NORM.get(cause, 1)
        corridor_tier = CORRIDOR_RISK_TIER_NORM.get(norm_cat(corridor), 1)
        veh_risk      = VEH_RISK_SCORE_NORM.get(veh_type, 1)

        # Corridor historical risk index (case-insensitive lookup)
        risk_lookup = self.metadata["corridor_risk_lookup"]
        risk_lookup_norm = {norm_cat(k): v for k, v in risk_lookup.items()}
        corridor_risk_index = risk_lookup_norm.get(norm_cat(corridor), 0.3)

        row = {
            "cause_score":          cause_score,
            "corridor_tier":        corridor_tier,
            "veh_risk":             veh_risk,
            "priority_num":         priority_high,
            "road_closure_num":     road_closure,
            "hour":                 hour,
            "day_of_week":          dow,
            "month":                month,
            "is_peak":              1 if hour in PEAK_HOURS else 0,
            "is_weekend":           1 if dow >= 5 else 0,
            "is_planned":           is_planned,
            "planned_duration_hrs": planned_dur,
            "corridor_risk_index":  corridor_risk_index,
            "event_cause_enc":      self._encode("event_cause", cause),
            "corridor_enc":         self._encode("corridor", corridor),
            "zone_enc":             self._encode("zone", zone),
            "veh_type_enc":         self._encode("veh_type", veh_type),
        }
        return pd.DataFrame([row])[FEATURE_COLS]

    # ── Prediction ──────────────────────────────────────────────────────────────

    def predict(self, event: dict) -> dict:
        """
        Full prediction for one event.
        Returns: severity, confidence, probabilities, duration estimate + range,
                 and top SHAP reasons.
        """
        X = self.build_features(event)

        # Severity classification
        proba = self.severity_model.predict_proba(X)[0]
        pred_int = int(np.argmax(proba))
        severity = INT_TO_SEVERITY[pred_int]
        confidence = float(proba[pred_int])
        prob_dict = {INT_TO_SEVERITY[i]: float(p) for i, p in enumerate(proba)}

        # Duration regression (model predicts log-minutes)
        log_dur = float(self.duration_model.predict(X)[0])
        duration_mins = float(np.expm1(log_dur))
        duration_mins = max(1.0, duration_mins)
        # Uncertainty band from training residual std
        resid_std = self.metadata.get("duration_resid_std", 0.5)
        dur_low  = max(1.0, float(np.expm1(log_dur - resid_std)))
        dur_high = float(np.expm1(log_dur + resid_std))

        # SHAP explanation
        reasons = self._explain_severity(X, pred_int)

        return {
            "severity":            severity,
            "confidence":          round(confidence, 3),
            "probabilities":       {k: round(v, 3) for k, v in prob_dict.items()},
            "duration_mins":       round(duration_mins, 1),
            "duration_range":      (round(dur_low, 1), round(dur_high, 1)),
            "top_reasons":         reasons,
        }

    # ── SHAP explainability ─────────────────────────────────────────────────────

    def _explain_severity(self, X: pd.DataFrame, pred_int: int, top_k: int = 3):
        """
        Returns the top_k features driving this prediction toward the
        predicted class, with signed contribution.
        """
        import shap

        if self._severity_explainer is None:
            self._severity_explainer = shap.TreeExplainer(self.severity_model)

        shap_values = self._severity_explainer.shap_values(X)

        # Multiclass: shap_values is list[n_classes] of (n_rows, n_feat) OR
        # a (n_rows, n_feat, n_classes) array depending on shap/lgbm version.
        if isinstance(shap_values, list):
            class_shap = shap_values[pred_int][0]
        else:
            arr = np.asarray(shap_values)
            if arr.ndim == 3:
                class_shap = arr[0, :, pred_int]
            else:
                class_shap = arr[0]

        contribs = []
        for feat, val in zip(FEATURE_COLS, class_shap):
            contribs.append((feat, float(val)))

        # Sort by absolute contribution toward the predicted class
        contribs.sort(key=lambda t: abs(t[1]), reverse=True)

        reasons = []
        for feat, val in contribs[:top_k]:
            reasons.append({
                "feature":      FEATURE_DISPLAY_NAMES.get(feat, feat),
                "raw_feature":  feat,
                "contribution": round(val, 4),
                "direction":    "increases" if val > 0 else "decreases",
                "value":        float(X.iloc[0][feat]),
            })
        return reasons

    # ── Model info ──────────────────────────────────────────────────────────────

    def get_model_info(self) -> dict:
        return {
            "severity_metrics": self.metadata.get("severity_metrics", {}),
            "duration_metrics": self.metadata.get("duration_metrics", {}),
            "trained_at":       self.metadata.get("trained_at", "unknown"),
            "n_train":          self.metadata.get("n_train", 0),
            "model_version":    self.metadata.get("model_version", "1.0"),
        }
