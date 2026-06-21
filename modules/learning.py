"""
Module 7 — Post-Event Learning Engine
Closes the loop the problem statement calls out: "No post-event learning system."

Logs every prediction; when the real event closes, records the actual outcome;
then computes accuracy trends and per-corridor duration correction factors that
nudge future predictions toward observed reality.

Storage: SQLite (single file, no server). Swap to a real DB later by changing
only the connection in _connect().
"""

import os
import sqlite3
import json
from datetime import datetime, timezone

from modules.data_pipeline import norm_cat
from utils.constants import LEARNING_DB_PATH

# A corridor needs at least this many resolved outcomes before we trust a
# correction factor for it (avoid overfitting to 1-2 events).
MIN_OUTCOMES_FOR_CORRECTION = 5
# Clamp correction factor so a few outliers can't wildly distort predictions.
CORRECTION_MIN, CORRECTION_MAX = 0.5, 2.0


class PostEventLearning:
    """
    Instantiate once. Call log_prediction() at predict time, record_outcome()
    when the event closes, and get_correction_factor()/get_accuracy_report()
    to read what the system has learned.
    """

    def __init__(self, db_path=LEARNING_DB_PATH):
        self.db_path = str(db_path)
        self._init_db()

    def _connect(self):
        # Ensure parent directory exists (critical on Render / fresh deployments)
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    prediction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at      TEXT NOT NULL,
                    event_cause     TEXT,
                    corridor        TEXT,
                    corridor_norm   TEXT,
                    hour            INTEGER,
                    day_of_week     INTEGER,
                    pred_severity   TEXT,
                    pred_confidence REAL,
                    pred_duration   REAL,
                    features_json   TEXT
                )
            """)
            try:
                con.execute("ALTER TABLE predictions ADD COLUMN event_category TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                con.execute("ALTER TABLE predictions ADD COLUMN event_subcategory TEXT")
            except sqlite3.OperationalError:
                pass
            con.execute("""
                CREATE TABLE IF NOT EXISTS outcomes (
                    outcome_id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    prediction_id     INTEGER NOT NULL,
                    recorded_at       TEXT NOT NULL,
                    actual_severity   TEXT,
                    actual_duration   REAL,
                    severity_correct  INTEGER,
                    duration_error    REAL,
                    actual_officers   INTEGER,
                    actual_barricades INTEGER,
                    actual_patrol_jeeps INTEGER,
                    actual_tow_vehicles INTEGER,
                    actual_command_vans INTEGER,
                    FOREIGN KEY (prediction_id) REFERENCES predictions(prediction_id)
                )
            """)
            # Migrate outcomes table if columns missing
            for col in [
                "actual_officers INTEGER",
                "actual_barricades INTEGER",
                "actual_patrol_jeeps INTEGER",
                "actual_tow_vehicles INTEGER",
                "actual_command_vans INTEGER",
            ]:
                try:
                    con.execute(f"ALTER TABLE outcomes ADD COLUMN {col}")
                except sqlite3.OperationalError:
                    pass
            # Migrate predictions table with predicted resource columns
            for col in [
                "pred_officers INTEGER",
                "pred_barricades INTEGER",
                "pred_patrol_jeeps INTEGER",
                "pred_tow_vehicles INTEGER",
                "pred_command_vans INTEGER",
            ]:
                try:
                    con.execute(f"ALTER TABLE predictions ADD COLUMN {col}")
                except sqlite3.OperationalError:
                    pass

    # ── Log a prediction ────────────────────────────────────────────────────────

    def log_prediction(self, event: dict, prediction: dict,
                        resource_plan: dict = None) -> int:
        """Record a prediction; returns its prediction_id (used to link outcome)."""
        rplan = resource_plan or {}
        with self._connect() as con:
            cur = con.execute(
                """INSERT INTO predictions
                   (created_at, event_cause, corridor, corridor_norm, hour,
                    day_of_week, pred_severity, pred_confidence, pred_duration,
                    features_json, event_category, event_subcategory,
                    pred_officers, pred_barricades, pred_patrol_jeeps,
                    pred_tow_vehicles, pred_command_vans)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    event.get("event_cause"),
                    event.get("corridor"),
                    norm_cat(event.get("corridor")),
                    event.get("hour"),
                    event.get("day_of_week"),
                    prediction.get("severity"),
                    prediction.get("confidence"),
                    prediction.get("duration_mins"),
                    json.dumps(event, default=str),
                    event.get("event_category"),
                    event.get("event_subcategory"),
                    rplan.get("total_officers"),
                    rplan.get("total_barricades"),
                    rplan.get("patrol_jeeps"),
                    rplan.get("tow_vehicles"),
                    rplan.get("command_vans"),
                ),
            )
            return cur.lastrowid

    # ── Record the actual outcome ───────────────────────────────────────────────

    def record_outcome(self, prediction_id: int,
                       actual_severity: str = None,
                       actual_duration_mins: float = None,
                       actual_officers: int = None,
                       actual_barricades: int = None,
                       actual_patrol_jeeps: int = None,
                       actual_tow_vehicles: int = None,
                       actual_command_vans: int = None) -> dict:
        """Log (or overwrite) the real outcome of a previously-predicted event."""
        with self._connect() as con:
            row = con.execute(
                "SELECT pred_severity, pred_duration FROM predictions WHERE prediction_id=?",
                (prediction_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"No prediction with id {prediction_id}")
            pred_sev, pred_dur = row

            sev_correct = (
                int(actual_severity == pred_sev)
                if actual_severity is not None else None
            )
            dur_error = (
                abs(actual_duration_mins - pred_dur)
                if (actual_duration_mins is not None and pred_dur is not None)
                else None
            )
            # Allow overwriting previous outcome for same prediction
            con.execute(
                "DELETE FROM outcomes WHERE prediction_id=?",
                (prediction_id,)
            )
            con.execute(
                """INSERT INTO outcomes
                   (prediction_id, recorded_at, actual_severity, actual_duration,
                    severity_correct, duration_error,
                    actual_officers, actual_barricades, actual_patrol_jeeps,
                    actual_tow_vehicles, actual_command_vans)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    prediction_id,
                    datetime.now(timezone.utc).isoformat(),
                    actual_severity, actual_duration_mins,
                    sev_correct, dur_error,
                    actual_officers, actual_barricades, actual_patrol_jeeps,
                    actual_tow_vehicles, actual_command_vans,
                ),
            )
        return {
            "prediction_id": prediction_id,
            "severity_correct": sev_correct,
            "duration_error_mins": round(dur_error, 1) if dur_error is not None else None,
        }

    # ── Learn: per-corridor duration correction factor ──────────────────────────

    def get_correction_factor(self, corridor: str) -> float:
        """
        Returns a multiplier for the duration model on this corridor, learned
        from observed actual/predicted ratios. 1.0 = no correction (default).
        Only applied once enough outcomes exist (else 1.0).
        """
        cn = norm_cat(corridor)
        with self._connect() as con:
            rows = con.execute(
                """SELECT p.pred_duration, o.actual_duration
                   FROM outcomes o JOIN predictions p
                     ON o.prediction_id = p.prediction_id
                   WHERE p.corridor_norm = ?
                     AND p.pred_duration > 0 AND o.actual_duration > 0""",
                (cn,),
            ).fetchall()

        if len(rows) < MIN_OUTCOMES_FOR_CORRECTION:
            return 1.0

        ratios = [actual / pred for pred, actual in rows]
        ratios.sort()
        median_ratio = ratios[len(ratios) // 2]
        return float(min(CORRECTION_MAX, max(CORRECTION_MIN, median_ratio)))

    def apply_correction(self, corridor: str, raw_duration_mins: float) -> float:
        """Apply the learned correction factor to a raw model duration."""
        return round(raw_duration_mins * self.get_correction_factor(corridor), 1)

    # ── Read what the system has learned ────────────────────────────────────────

    def get_accuracy_report(self) -> dict:
        """Aggregate accuracy across all scored outcomes — for the dashboard."""
        with self._connect() as con:
            total_pred = con.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
            total_out  = con.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
            sev = con.execute(
                "SELECT AVG(severity_correct) FROM outcomes WHERE severity_correct IS NOT NULL"
            ).fetchone()[0]
            dur = con.execute(
                "SELECT AVG(duration_error), "
                "       (SELECT duration_error FROM outcomes "
                "        WHERE duration_error IS NOT NULL "
                "        ORDER BY duration_error LIMIT 1 "
                "        OFFSET (SELECT COUNT(*)/2 FROM outcomes WHERE duration_error IS NOT NULL)) "
                "FROM outcomes WHERE duration_error IS NOT NULL"
            ).fetchone()

        return {
            "total_predictions":   int(total_pred),
            "total_outcomes":      int(total_out),
            "severity_accuracy":   round(sev, 3) if sev is not None else None,
            "mean_duration_error_mins":   round(dur[0], 1) if dur[0] is not None else None,
            "median_duration_error_mins": round(dur[1], 1) if dur[1] is not None else None,
        }

    def get_corridor_corrections(self) -> list:
        """All corridors that have a learned correction factor (for transparency)."""
        with self._connect() as con:
            corridors = [r[0] for r in con.execute(
                "SELECT DISTINCT corridor_norm FROM predictions WHERE corridor_norm IS NOT NULL"
            ).fetchall()]
        out = []
        for cn in corridors:
            cf = self.get_correction_factor(cn)
            if cf != 1.0:
                out.append({"corridor": cn, "correction_factor": round(cf, 3)})
        return sorted(out, key=lambda x: abs(x["correction_factor"] - 1.0), reverse=True)

    def get_comparison_data(self, limit: int = 50) -> list:
        """Return predicted vs. actually deployed resources for recorded outcomes."""
        with self._connect() as con:
            rows = con.execute(
                """SELECT
                    o.outcome_id,
                    p.prediction_id,
                    p.created_at,
                    p.event_cause,
                    p.corridor,
                    p.pred_severity,
                    p.pred_duration,
                    p.pred_officers,
                    p.pred_barricades,
                    p.pred_patrol_jeeps,
                    p.pred_tow_vehicles,
                    p.pred_command_vans,
                    o.actual_severity,
                    o.actual_duration,
                    o.actual_officers,
                    o.actual_barricades,
                    o.actual_patrol_jeeps,
                    o.actual_tow_vehicles,
                    o.actual_command_vans,
                    o.severity_correct,
                    o.duration_error
                   FROM outcomes o
                   JOIN predictions p ON o.prediction_id = p.prediction_id
                   ORDER BY o.outcome_id DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        cols = [
            "outcome_id", "prediction_id", "created_at", "event_cause", "corridor",
            "pred_severity", "pred_duration",
            "pred_officers", "pred_barricades", "pred_patrol_jeeps",
            "pred_tow_vehicles", "pred_command_vans",
            "actual_severity", "actual_duration",
            "actual_officers", "actual_barricades", "actual_patrol_jeeps",
            "actual_tow_vehicles", "actual_command_vans",
            "severity_correct", "duration_error"
        ]
        return [dict(zip(cols, row)) for row in rows]

    def reset(self):
        """Wipe all logs (useful for demo resets)."""
        with self._connect() as con:
            con.execute("DROP TABLE IF EXISTS outcomes")
            con.execute("DROP TABLE IF EXISTS predictions")
        self._init_db()

