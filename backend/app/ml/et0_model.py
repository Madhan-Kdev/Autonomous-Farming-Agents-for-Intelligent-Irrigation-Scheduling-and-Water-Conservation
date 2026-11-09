"""
Machine Learning ET0 Prediction Model.

Implements a Gradient Boosting Regressor trained on agro-meteorological features
to predict daily reference evapotranspiration (ET0) in mm/day.

Features:
- Maximum temperature (°C)
- Minimum temperature (°C)
- Mean temperature (°C)
- Diurnal temperature range (Tmax - Tmin, °C)
- Mean relative humidity (%)
- Wind speed at 2m (m/s)
- Solar radiation (MJ/m²/day)
- Surface pressure (kPa)
- Day of year (1-366)

Ground Truth:
    Trained against the analytical FAO-56 Penman-Monteith physics equation
    (Allen et al., 1998) across global agricultural climate distributions.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.service.et0_calculator import ET0Inputs, FAO56PenmanMonteith

logger = logging.getLogger(__name__)

FEATURE_NAMES = [
    "temp_max_c",
    "temp_min_c",
    "temp_mean_c",
    "temp_range_c",
    "humidity_mean_pct",
    "wind_speed_m_s",
    "solar_radiation_mj_m2",
    "pressure_kpa",
    "day_of_year",
]


class ET0MLModel:
    """
    Trained machine learning model pipeline for ET0 estimation.

    Provides fast, empirical ET0 inference and robust fallback when full
    atmospheric radiation variables are difficult to compute.
    """

    def __init__(self) -> None:
        self.model_name = "GradientBoostingRegressor (scikit-learn)"
        self.pipeline: Pipeline | None = None
        self._is_trained = False
        self.train_r2_score: float = 0.0
        self.train_rmse: float = 0.0

    def is_trained(self) -> bool:
        return self._is_trained

    def train(self, n_samples: int = 1200, random_seed: int = 42) -> None:
        """
        Generate diverse agricultural weather scenarios, compute analytical
        FAO-56 Penman-Monteith target values, and train the model pipeline.
        """
        logger.info("Training ET0 ML model on %d synthetic FAO-56 samples...", n_samples)
        rng = np.random.default_rng(random_seed)

        # 1. Generate diverse meteorological input features
        t_min = rng.uniform(2.0, 26.0, n_samples)
        t_range = rng.uniform(6.0, 20.0, n_samples)
        t_max = t_min + t_range
        t_mean = (t_max + t_min) / 2.0

        rh_mean = rng.uniform(20.0, 90.0, n_samples)
        wind = rng.uniform(0.5, 6.5, n_samples)
        solar = rng.uniform(6.0, 28.0, n_samples)
        pressure = rng.uniform(92.0, 102.0, n_samples)
        doy = rng.integers(1, 366, n_samples)
        lat_deg = rng.uniform(10.0, 45.0, n_samples)
        altitude_m = rng.uniform(50.0, 1000.0, n_samples)

        # 2. Compute ground truth FAO-56 PM ET0 targets
        calc = FAO56PenmanMonteith()
        y = np.empty(n_samples, dtype=np.float64)

        for idx in range(n_samples):
            inp = ET0Inputs(
                temp_max_c=float(t_max[idx]),
                temp_min_c=float(t_min[idx]),
                humidity_max_pct=float(min(100.0, rh_mean[idx] + 15.0)),
                humidity_min_pct=float(max(10.0, rh_mean[idx] - 15.0)),
                humidity_mean_pct=float(rh_mean[idx]),
                wind_speed_m_s=float(wind[idx]),
                solar_radiation_mj_m2=float(solar[idx]),
                latitude_rad=math.radians(float(lat_deg[idx])),
                altitude_m=float(altitude_m[idx]),
                day_of_year=int(doy[idx]),
                pressure_kpa=float(pressure[idx]),
            )
            y[idx] = calc.compute(inp)

        # 3. Assemble feature matrix X
        X = np.column_stack([
            t_max,
            t_min,
            t_mean,
            t_range,
            rh_mean,
            wind,
            solar,
            pressure,
            doy,
        ])

        # 4. Train Scikit-Learn Pipeline
        self.pipeline = Pipeline([
            ("scaler", StandardScaler()),
            (
                "regressor",
                GradientBoostingRegressor(
                    n_estimators=120,
                    max_depth=4,
                    learning_rate=0.08,
                    subsample=0.9,
                    random_state=random_seed,
                ),
            ),
        ])

        self.pipeline.fit(X, y)
        self._is_trained = True

        # 5. Evaluate Performance Metrics
        y_pred = self.pipeline.predict(X)
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        self.train_r2_score = round(1.0 - (ss_res / ss_tot), 4)
        self.train_rmse = round(float(np.sqrt(np.mean((y - y_pred) ** 2))), 4)

        logger.info(
            "ET0 ML Model training completed: R² = %.4f, RMSE = %.4f mm/day",
            self.train_r2_score,
            self.train_rmse,
        )

    def predict(self, weather_data: dict[str, Any], day_of_year: int = 180) -> tuple[float, float]:
        """
        Predict ET0 from weather data dictionary.

        Returns
        -------
        tuple[float, float]
            (predicted_et0_mm, prediction_confidence)
        """
        if not self._is_trained or self.pipeline is None:
            self.train()

        assert self.pipeline is not None

        # Extract features with sensible agricultural fallbacks
        missing_count = 0

        t_max = weather_data.get("temperature_max_c")
        if t_max is None:
            t_max = 30.0
            missing_count += 1

        t_min = weather_data.get("temperature_min_c")
        if t_min is None:
            t_min = 18.0
            missing_count += 1

        t_mean = weather_data.get("temperature_mean_c")
        if t_mean is None:
            t_mean = (t_max + t_min) / 2.0

        t_range = t_max - t_min

        rh_mean = weather_data.get("humidity_mean_pct")
        if rh_mean is None:
            rh_mean = 55.0
            missing_count += 1

        wind = weather_data.get("wind_speed_m_s")
        if wind is None:
            wind = 2.0
            missing_count += 1

        solar = weather_data.get("solar_radiation_mj_m2")
        if solar is None:
            solar = 20.0
            missing_count += 1

        pressure = weather_data.get("pressure_kpa")
        if pressure is None:
            pressure = 100.0

        doy = day_of_year

        x_in = np.array([
            [
                float(t_max),
                float(t_min),
                float(t_mean),
                float(t_range),
                float(rh_mean),
                float(wind),
                float(solar),
                float(pressure),
                float(doy),
            ]
        ])

        pred_val = float(self.pipeline.predict(x_in)[0])
        pred_val = max(0.0, round(pred_val, 3))

        # Confidence heuristic: base on R² and feature completeness
        base_confidence = min(0.98, self.train_r2_score)
        confidence = max(0.40, base_confidence - (missing_count * 0.12))

        return pred_val, round(confidence, 2)


# ================================================================== #
# Global Cached Singleton
# ================================================================== #

_MODEL_INSTANCE: ET0MLModel | None = None


def get_et0_model() -> ET0MLModel:
    """Return singleton instance of ET0MLModel (trained on first access)."""
    global _MODEL_INSTANCE
    if _MODEL_INSTANCE is None:
        _MODEL_INSTANCE = ET0MLModel()
        _MODEL_INSTANCE.train()
    return _MODEL_INSTANCE

