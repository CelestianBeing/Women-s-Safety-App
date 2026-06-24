"""
AI risk prediction using a Random Forest trained on synthetic + historical data.
"""
import os
import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score
import joblib

from config import Config

logger = logging.getLogger(__name__)

FEATURE_COLS = ['hour', 'day', 'road_type', 'lighting',
                'police_dist', 'crowd_density', 'recent_reports']

_model_cache = None   # in-process cache to avoid repeated disk reads


# ── Training data ─────────────────────────────────────────────────────────────

def generate_training_data(n_samples: int = 8000) -> pd.DataFrame:
    """Synthetic dataset encoding domain knowledge about pedestrian risk."""
    rng = np.random.default_rng(42)

    hour          = rng.integers(0,  24, n_samples)
    day           = rng.integers(0,   7, n_samples)
    road_type     = rng.choice([0, 1, 2, 3], n_samples, p=[0.2, 0.3, 0.4, 0.1])
    lighting      = rng.choice([0, 1, 2, 3], n_samples, p=[0.3, 0.3, 0.2, 0.2])
    police_dist   = rng.exponential(300, n_samples).clip(0, 2000)
    crowd_density = rng.uniform(0, 100, n_samples)
    rec_reports   = rng.poisson(2, n_samples).clip(0, 30)

    is_night        = (hour >= 21) | (hour <= 4)
    is_late_night   = (hour >= 23) | (hour <= 3)
    is_weekend      = day >= 5
    no_lighting     = lighting == 3
    poor_lighting   = lighting >= 2
    isolated_road   = road_type == 3

    risk = (
        35  * is_late_night.astype(float) +
        15  * is_night.astype(float) +
        8   * (is_night & is_weekend).astype(float) +
        20  * no_lighting.astype(float) +
        10  * poor_lighting.astype(float) +
        12  * isolated_road.astype(float) +
        -0.025 * police_dist.clip(0, 800) +
        0.10  * crowd_density * is_night.astype(float) +   # crowds at night = risk
        -0.03 * crowd_density * (~is_night).astype(float) + # crowds in day = safer
        3.5   * rec_reports +
        rng.normal(0, 4, n_samples)
    )

    X = pd.DataFrame({
        'hour':           hour,
        'day':            day,
        'road_type':      road_type,
        'lighting':       lighting,
        'police_dist':    police_dist,
        'crowd_density':  crowd_density,
        'recent_reports': rec_reports,
        'risk':           np.clip(risk, 0, 100),
    })
    return X


# ── Model lifecycle ───────────────────────────────────────────────────────────

def train_model(save: bool = True) -> RandomForestRegressor:
    """Train a Random Forest on synthetic data, optionally save to disk."""
    logger.info("Training risk prediction model…")
    df  = generate_training_data()
    X   = df[FEATURE_COLS]
    y   = df['risk']

    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=5,
        n_jobs=-1,
        random_state=42,
    )
    model.fit(X, y)

    # Quick sanity check
    scores = cross_val_score(model, X, y, cv=3, scoring='r2')
    logger.info("CV R² scores: %s  (mean %.3f)", scores.round(3), scores.mean())

    if save:
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        joblib.dump(model, Config.MODEL_FILE)
        logger.info("Model saved to %s", Config.MODEL_FILE)

    return model


def load_model() -> RandomForestRegressor:
    """Return cached model, loading from disk or training if absent."""
    global _model_cache
    if _model_cache is not None:
        return _model_cache
    if os.path.exists(Config.MODEL_FILE):
        logger.info("Loading model from %s", Config.MODEL_FILE)
        _model_cache = joblib.load(Config.MODEL_FILE)
    else:
        _model_cache = train_model(save=True)
    return _model_cache


# ── Inference ─────────────────────────────────────────────────────────────────

def predict_risk(hour: int, day: int, road_type: int, lighting: int,
                 police_dist: float, crowd_density: float,
                 recent_reports: int) -> float:
    """Return predicted risk score 0–100 for the given feature vector."""
    model = load_model()
    X = pd.DataFrame([[
        int(hour), int(day), int(road_type), int(lighting),
        float(police_dist), float(crowd_density), int(recent_reports),
    ]], columns=FEATURE_COLS)
    return float(np.clip(model.predict(X)[0], 0, 100))
