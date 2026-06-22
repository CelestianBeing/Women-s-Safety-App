import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import joblib
import os
from config import Config

def generate_training_data(n_samples=5000):
    """Create synthetic historical data for AI risk prediction."""
    np.random.seed(42)
    # Features: hour, day_of_week, road_type_encoded (0-3), lighting_level (0-3),
    # proximity_to_police (0-1000m), crowd_density (0-100), recent_reports (0-20)
    # Target: risk_score 0-100
    X = np.zeros((n_samples, 7))
    # hour: 0-23
    X[:, 0] = np.random.randint(0, 24, n_samples)
    # day: 0-6
    X[:, 1] = np.random.randint(0, 7, n_samples)
    # road type: 0=primary, 1=secondary, 2=residential, 3=path
    X[:, 2] = np.random.choice([0,1,2,3], n_samples, p=[0.2,0.3,0.4,0.1])
    # lighting: 0=good, 1=moderate, 2=poor, 3=none
    X[:, 3] = np.random.choice([0,1,2,3], n_samples, p=[0.3,0.3,0.2,0.2])
    # police proximity
    X[:, 4] = np.random.exponential(200, n_samples)
    # crowd density
    X[:, 5] = np.random.triangular(0, 30, 100, n_samples)
    # recent reports in area
    X[:, 6] = np.random.poisson(2, n_samples)

    # Risk formula (higher = more dangerous)
    risk = (
        0.5 * (X[:, 0] >= 20) * 30 +  # late night
        0.3 * (X[:, 0] >= 22) * 20 +
        0.2 * (X[:, 1] >= 5) * 10 +   # weekend night
        -0.02 * np.clip(X[:, 4], 0, 500) +
        0.3 * X[:, 6] * 5 +
        0.15 * X[:, 5] * (X[:, 0] >= 20) +
        0.1 * (X[:, 3] == 3) * 40 +
        0.05 * (X[:, 2] == 3) * 20 +
        np.random.normal(0, 5, n_samples)
    )
    risk = np.clip(risk, 0, 100)
    columns = ['hour', 'day', 'road_type', 'lighting', 'police_dist', 'crowd_density', 'recent_reports']
    df = pd.DataFrame(X, columns=columns)
    df['risk'] = risk
    return df

def train_model():
    df = generate_training_data()
    X = df.drop('risk', axis=1)
    y = df['risk']
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)
    joblib.dump(model, Config.MODEL_FILE)
    print("Model trained and saved.")
    return model

def load_model():
    if not os.path.exists(Config.MODEL_FILE):
        return train_model()
    return joblib.load(Config.MODEL_FILE)

def predict_risk(hour, day, road_type, lighting, police_dist, crowd_density, recent_reports):
    model = load_model()
    X = pd.DataFrame([[hour, day, road_type, lighting, police_dist, crowd_density, recent_reports]],
                     columns=['hour', 'day', 'road_type', 'lighting', 'police_dist', 'crowd_density', 'recent_reports'])
    return model.predict(X)[0]