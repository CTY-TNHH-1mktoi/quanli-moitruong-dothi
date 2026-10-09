"""Load the bundled Random Forests and classify one environment reading."""

from functools import lru_cache
import math
from pathlib import Path

import joblib
import pandas as pd


MODEL_PATH = Path(__file__).with_name("environment_rf.joblib")
FEATURE_FIELDS = (
    ("pm25", "PM25"),
    ("pm10", "PM10"),
    ("temperature_c", "NhietDo"),
    ("humidity_pct", "DoAm"),
    ("noise_db", "TiengOn"),
)
AIR_LABELS = {
    "Tot": "Tốt",
    "Trung binh": "Trung bình",
    "Kem": "Kém",
    "Nguy hai": "Nguy hại",
}
NOISE_LABELS = {
    "Yen tinh": "Yên tĩnh",
    "On vua": "Ồn vừa",
    "On cao": "Ồn cao",
}


@lru_cache(maxsize=1)
def load_model():
    """Only load a model file shipped with this project, once per process."""
    bundle = joblib.load(MODEL_PATH)
    if bundle.get("features") != [name for name, _ in FEATURE_FIELDS]:
        raise ValueError("Model features do not match the application inputs")
    if "air_quality_model" not in bundle or "noise_level_model" not in bundle:
        raise ValueError("Model bundle is missing a classifier")
    return bundle


def predict_environment(readings):
    """Return demo classifications only when all five source values are usable."""
    values = {}
    missing = []
    for feature, field in FEATURE_FIELDS:
        try:
            value = float(readings[field])
            if not math.isfinite(value):
                raise ValueError("non-finite reading")
        except (KeyError, TypeError, ValueError):
            missing.append(field)
        else:
            values[feature] = value

    if missing:
        return {"TrangThai": "thieu_du_lieu", "Thieu": missing}

    bundle = load_model()
    sample = pd.DataFrame([values], columns=bundle["features"])
    air = str(bundle["air_quality_model"].predict(sample)[0])
    noise = str(bundle["noise_level_model"].predict(sample)[0])
    return {
        "TrangThai": "ok",
        "ChatLuongKhongKhi": AIR_LABELS.get(air, air),
        "MucTiengOn": NOISE_LABELS.get(noise, noise),
    }
