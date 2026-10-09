"""Download iSCAPE sensor CSVs and train small air/noise Random Forests.

The labels are generated from transparent demo thresholds, not expert-annotated
ground truth. Training writes environment_rf_metadata.json with evaluation details.
"""
from pathlib import Path
import json
import urllib.request

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline as sklearn_make_pipeline
from sklearn.impute import SimpleImputer

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "iscape_data"
MODEL_PATH = ROOT / "environment_rf.joblib"
META_PATH = ROOT / "environment_rf_metadata.json"
RECORD_ID = "3570680"  # iSCAPE Citizen Science Workshops Data (CC BY 4.0)
FILES = [
    "5129.csv", "5464.csv", "9561.csv", "5271.csv", "5121.csv", "5434.csv",
    "5164.csv", "5391.csv", "5630.csv", "5104.csv", "5117.csv",
    "5124.csv", "5110.csv", "5101.csv", "5165.csv", "5397.csv", "5109.csv",
    "5258.csv",
]
FEATURES = ["pm25", "pm10", "temperature_c", "humidity_pct", "noise_db"]
AIR_CLASSES = ["Tot", "Trung binh", "Kem", "Nguy hai"]
NOISE_CLASSES = ["Yen tinh", "On vua", "On cao"]


def ensure_data():
    DATA_DIR.mkdir(exist_ok=True)
    if all((DATA_DIR / name).exists() for name in FILES):
        return
    record = json.load(urllib.request.urlopen(f"https://zenodo.org/api/records/{RECORD_ID}", timeout=60))
    by_name = {f["key"]: f for f in record["files"]}
    for name in FILES:
        path = DATA_DIR / name
        if not path.exists() or path.stat().st_size != by_name[name]["size"]:
            print(f"Downloading {name}...", flush=True)
            urllib.request.urlretrieve(by_name[name]["links"]["self"], path)


def load_sensor_data():
    ensure_data()
    chunks = []
    for name in FILES:
        raw = pd.read_csv(DATA_DIR / name, usecols=lambda c: c in {
            "EXT_PM_25", "EXT_PM_10", "TEMP", "HUM", "NOISE_A"
        }, low_memory=False)
        if not {"EXT_PM_25", "EXT_PM_10", "TEMP", "HUM", "NOISE_A"}.issubset(raw.columns):
            print(f"Skipping {name}: required fields missing")
            continue
        part = pd.DataFrame({
            "pm25": pd.to_numeric(raw["EXT_PM_25"], errors="coerce"),
            "pm10": pd.to_numeric(raw["EXT_PM_10"], errors="coerce"),
            "temperature_c": pd.to_numeric(raw["TEMP"], errors="coerce"),
            "humidity_pct": pd.to_numeric(raw["HUM"], errors="coerce"),
            "noise_db": pd.to_numeric(raw["NOISE_A"], errors="coerce"),
        }).dropna()
        # Remove physically implausible readings and obvious sensor spikes.
        part = part[
            part.pm25.between(0, 1000) & part.pm10.between(0, 1500)
            & part.temperature_c.between(-20, 60) & part.humidity_pct.between(0, 100)
            & part.noise_db.between(20, 120)
        ]
        if len(part) > 30000:
            part = part.sample(n=30000, random_state=42)
        part["source_file"] = name
        chunks.append(part)
        print(f"Prepared {name}: {len(part):,} readings", flush=True)
    if not chunks:
        raise RuntimeError("No CSVs with all five required sensor fields were found.")
    return pd.concat(chunks, ignore_index=True)


def make_pipeline():
    return sklearn_make_pipeline(
        SimpleImputer(strategy="median"),
        RandomForestClassifier(
            n_estimators=120, max_depth=14, min_samples_leaf=3,
            class_weight="balanced", random_state=42, n_jobs=-1,
        ),
    )


def fit_one(X, y, classes):
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    model = make_pipeline()
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    return model, {
        "test_report_text": classification_report(
            y_test, pred, labels=classes, zero_division=0
        ),
        "classification_report": classification_report(
            y_test, pred, labels=classes, zero_division=0, output_dict=True
        ),
        "confusion_matrix": confusion_matrix(y_test, pred, labels=classes).tolist(),
    }


def main():
    data = load_sensor_data()
    X = data[FEATURES]
    # Demo rule labels. PM2.5 bins approximate severity bands; the dataset is
    # minute-level, so this is not an official 24-hour AQI calculation.
    pm = data.pm25.to_numpy()
    y_air = np.select([pm <= 12, pm <= 35.4, pm <= 150], AIR_CLASSES[:3], default=AIR_CLASSES[3])
    # Simple sound-level bands for a prototype alert; adjust to the project's
    # intended indoor/outdoor use and local standard before making health claims.
    db = data.noise_db.to_numpy()
    y_noise = np.select([db < 55, db < 70], NOISE_CLASSES[:2], default=NOISE_CLASSES[2])

    air_model, air_eval = fit_one(X, y_air, AIR_CLASSES)
    noise_model, noise_eval = fit_one(X, y_noise, NOISE_CLASSES)
    bundle = {
        "air_quality_model": air_model,
        "noise_level_model": noise_model,
        "features": FEATURES,
        "air_classes": AIR_CLASSES,
        "noise_classes": NOISE_CLASSES,
    }
    joblib.dump(bundle, MODEL_PATH)
    counts = {
        "air": pd.Series(y_air).value_counts().reindex(AIR_CLASSES, fill_value=0).to_dict(),
        "noise": pd.Series(y_noise).value_counts().reindex(NOISE_CLASSES, fill_value=0).to_dict(),
    }
    metadata = {
        "dataset": "iSCAPE Citizen Science Workshops Data",
        "dataset_url": "https://zenodo.org/records/3570680",
        "license": "CC BY 4.0",
        "source_files": FILES,
        "rows_used": int(len(data)),
        "features": FEATURES,
        "air_classes": AIR_CLASSES,
        "air_label_rule": "PM2.5 <=12: Tot; <=35.4: Trung binh; <=150: Kem; >150: Nguy hai (demo thresholds, not official minute-level AQI).",
        "noise_classes": NOISE_CLASSES,
        "noise_label_rule": "<55 dBA: Yen tinh; 55-<70 dBA: On vua; >=70 dBA: On cao (prototype bands; choose thresholds for deployment setting).",
        "class_counts": counts,
        "air_test_metrics": air_eval,
        "noise_test_metrics": noise_eval,
        "warning": "Targets are rule-generated from the sensor readings. Test scores measure reproduction of those thresholds, not independent expert accuracy or medical/environmental advice. Data are iSCAPE European citizen-science readings; local sensor calibration and local thresholds are still needed.",
    }
    META_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nRows used:", f"{len(data):,}")
    print("Air class counts:", counts["air"])
    print("Noise class counts:", counts["noise"])
    print("Air test report:\n", air_eval["test_report_text"])
    print("Noise test report:\n", noise_eval["test_report_text"])
    print(f"Saved model: {MODEL_PATH.name}")
    print(f"Saved metadata: {META_PATH.name}")


if __name__ == "__main__":
    main()
