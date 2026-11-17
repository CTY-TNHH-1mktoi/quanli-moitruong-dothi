"""Prepare bounded, source-traceable dialogue examples from historical sensors.

This teaches reading supplied values and consultation, not a forecasting model.
Source CSVs are streamed; no live readings or invented AQI labels are produced.
"""

from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import random
import re
import shutil
import time
from uuid import uuid4
import zipfile

import requests

from prepare_xanhnon_data import make_record, normalize, stable_id


ROOT = Path(__file__).resolve().parent
SOURCES = [
    {"id": "iscape_outdoor", "record": "3570700", "priority": 1,
     "title": "iSCAPE Outdoor Sensor Deployment Data", "url": "https://zenodo.org/records/3570700"},
    {"id": "iscape_workshops", "record": "3570680", "priority": 2,
     "title": "iSCAPE Citizen Science Workshops Data", "url": "https://zenodo.org/records/3570680"},
    {"id": "iscape_development", "record": "3570688", "priority": 3,
     "title": "iSCAPE Low Cost Sensor Development Data", "url": "https://zenodo.org/records/3570688"},
    {"id": "beijing_air", "priority": 4, "license": "CC-BY-4.0",
     "title": "Beijing Multi-Site Air Quality", "url": "https://archive.ics.uci.edu/dataset/501/beijingmultisiteairqualitydata",
     "download": "https://archive.ics.uci.edu/static/public/501/beijing%2Bmulti%2Bsite%2Bair%2Bquality%2Bdata.zip"},
]
ALIASES = {
    "pm25": ("EXTPM25", "PM25", "EXTPMA25", "EXTPMB25"),
    "pm10": ("EXTPM10", "PM10", "EXTPMA10", "EXTPMB10"),
    "temperature": ("TEMP", "TEMPERATURE"),
    "humidity": ("HUM", "HUMIDITY", "RELATIVEHUMIDITY"),
    "noise": ("NOISEA", "NOISELEVELDBA", "NOISEDBA"),
}
BOUNDS = {"pm25": (0, 5000), "pm10": (0, 5000), "temperature": (-60, 80),
          "humidity": (0, 100), "noise": (0, 160)}


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + uuid4().hex + '.new')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Windows readers/antivirus can briefly deny replacing an open target.
        # Keep the original intact and retry the atomic replacement only.
        for attempt in range(8):
            try:
                temporary.replace(path)
                break
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(min(.05 * 2**attempt, .5))
    finally:
        temporary.unlink(missing_ok=True)


def digest(path, algorithm="sha256"):
    hasher = hashlib.new(algorithm)
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def request(url, *, stream=False):
    """Bounded retries; a failed fetch remains visible instead of fake completion."""
    for attempt in range(4):
        try:
            response = requests.get(url, stream=stream, timeout=(15, 60),
                                    headers={"User-Agent": "XanhNon-project-dataset-preparation/1.0"})
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                response.close()
                time.sleep((3, 10, 30)[attempt])
                continue
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep((3, 10, 30)[attempt])


def download(entry, target, existing=()):
    """Reuse matching cached content, irrespective of filename; verify upstream MD5."""
    target = Path(target)
    checksum = entry.get("checksum")
    algorithm, expected = checksum.split(":", 1) if checksum else (None, None)
    for path in [target, *existing]:
        path = Path(path)
        if not path.is_file() or (entry.get("size") and path.stat().st_size != entry["size"]):
            continue
        if expected and digest(path, algorithm) == expected:
            return path, "reused_verified_file"
        if path == target and not expected:
            sidecar = target.with_suffix(target.suffix + ".sha256")
            if sidecar.is_file() and digest(path) == sidecar.read_text().strip():
                return path, "reused_verified_file"
    target.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(target.parent).free < 3 * 2**30 + entry.get("size", 0):
        raise RuntimeError("Not enough storage for sensor sources; previous files were preserved")
    temporary = target.with_suffix(target.suffix + ".download")
    with request(entry["url"], stream=True) as response, temporary.open("wb") as stream:
        for chunk in response.iter_content(1024 * 1024):
            stream.write(chunk)
    if entry.get("size") and temporary.stat().st_size != entry["size"]:
        raise ValueError("Source size mismatch: " + entry["key"])
    if expected and digest(temporary, algorithm) != expected:
        raise ValueError("Source checksum mismatch: " + entry["key"])
    temporary.replace(target)
    target.with_suffix(target.suffix + ".sha256").write_text(digest(target), encoding="ascii")
    return target, "downloaded_verified_file" if expected else "downloaded_local_hash_recorded"


def file_family(name):
    return re.sub(r"_processed(?=\.csv$)", "", name.lower())


def plan_files(files):
    """Try the author-processed variant first, keep raw as a fallback only."""
    groups = defaultdict(list)
    for entry in files:
        if entry["key"].lower().endswith(".csv"):
            groups[file_family(entry["key"])].append(entry)
    return [sorted(group, key=lambda item: ("processed" not in item["key"].lower(), item["key"]))
            for _, group in sorted(groups.items())]


def parse_observation(row):
    columns = {re.sub(r"[^A-Z0-9]", "", str(key).upper()): value for key, value in row.items()}
    values, channels = {}, {}
    for field, aliases in ALIASES.items():
        for alias in aliases:
            try:
                value = float(columns[alias])
            except (KeyError, TypeError, ValueError):
                continue
            low, high = BOUNDS[field]
            if math.isfinite(value) and low <= value <= high:
                values[field], channels[field] = round(value, 1), alias
                break
    # A failed particulate mass consistency check is unsuitable as a teaching example.
    if values.get("pm25", 0) > values.get("pm10", 5000) + 1:
        return None
    if len(values) < 2:
        return None
    timestamp = row.get("Time") or row.get("TIME")
    if not timestamp and all(str(row.get(key, "")).strip() for key in ("year", "month", "day", "hour")):
        timestamp = "-".join(str(row[key]) for key in ("year", "month", "day")) + " " + str(row["hour"])
    return {"values": values, "channels": channels, "timestamp": timestamp,
            "station": row.get("station")}


def observation_key(observation):
    # The model sees rounded input values. Repeated vectors teach the same thing,
    # even if they occurred at another time or were copied to another dataset.
    return stable_id(json.dumps(observation["values"], sort_keys=True))


def sample_csv(stream, source, filename, limit=64):
    rng, samples, seen, counts = random.Random(42), [], set(), Counter()
    for row in csv.DictReader(stream):
        counts["rows_scanned"] += 1
        observation = parse_observation(row)
        if observation is None:
            counts["unusable_rows"] += 1
            continue
        key = observation_key(observation)
        if key in seen:
            counts["repeated_measurements"] += 1
            continue
        # Keep bounded memory per recording; exact selected vectors are deduped again globally.
        if len(seen) < 100000:
            seen.add(key)
        counts["eligible_rows"] += 1
        observation.update({"source": source["id"], "filename": filename,
                            "group": source["id"] + ":" + file_family(filename), "key": key})
        index = counts["eligible_rows"]
        if len(samples) < limit:
            samples.append(observation)
        else:
            chosen = rng.randrange(index)
            if chosen < limit:
                samples[chosen] = observation
    return samples, dict(counts)


@contextmanager
def archive_csvs(path):
    """Read ZIP members without extracting untrusted paths or unrelated files."""
    with zipfile.ZipFile(path) as archive:
        members = sorted(archive.namelist())
        csv_members = [name for name in members if re.search(r"(?:^|/)PRSA_Data_.*\.csv$", name)]
        if csv_members:
            yield archive, csv_members
            return
        nested = next((name for name in members if Path(name).name == "PRSA2017_Data_20130301-20170228.zip"), None)
        if nested is None or archive.getinfo(nested).file_size > 50 * 2**20:
            raise ValueError("Expected UCI source archive not found")
        with zipfile.ZipFile(io.BytesIO(archive.read(nested))) as inner:
            csv_members = sorted(name for name in inner.namelist() if re.search(r"(?:^|/)PRSA_Data_.*\.csv$", name))
            if not csv_members:
                raise ValueError("Expected UCI station recordings not found")
            yield inner, csv_members


def collect_sources(storage, notify=lambda value: None):
    storage = Path(storage)
    samples, reports, seen_files = [], [], {}
    existing = list((ROOT / "iscape_data").glob("*.csv"))
    for source in SOURCES:
        notify({"phase": "preparing_source", "source": source["id"]})
        report = {**source, "files": [], "skipped": [], "sampling": "Up to 64 valid, distinct vectors per recording"}
        if source.get("record"):
            metadata_path = storage / "metadata" / (source["record"] + ".json")
            if metadata_path.is_file():
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            else:
                with request("https://zenodo.org/api/records/" + source["record"]) as response:
                    metadata = response.json()
                save_json(metadata_path, metadata)
            report["license"] = metadata["metadata"].get("license", {}).get("id")
            if report["license"] not in ("cc-zero", "cc-by-4.0"):
                raise ValueError("Source license needs review: " + source["id"])
            report["metadata_sha256"] = digest(metadata_path)
            for variants in plan_files(metadata["files"]):
                usable = False
                for raw in variants:
                    name, checksum = raw["key"], raw.get("checksum")
                    if usable:
                        report["skipped"].append({"file": name, "reason": "author_processed_variant_already_usable"})
                        continue
                    if checksum and checksum in seen_files:
                        report["skipped"].append({"file": name, "reason": "identical_file_content", "retained": seen_files[checksum]})
                        continue
                    entry = {**raw, "url": raw["links"]["self"]}
                    path, action = download(entry, storage / source["id"] / name, existing)
                    with path.open("r", encoding="utf-8-sig", newline="") as stream:
                        rows, statistics = sample_csv(stream, source, name)
                    report["files"].append({"file": name, "path": str(path), "sha256": digest(path),
                                            "upstream_checksum": checksum, "action": action, **statistics})
                    if checksum:
                        seen_files[checksum] = source["id"] + "/" + name
                    samples.extend(rows)
                    usable = bool(rows)
        else:
            entry = {"key": "beijing-multisite.zip", "url": source["download"]}
            path, action = download(entry, storage / source["id"] / entry["key"])
            report["archive"] = {"path": str(path), "sha256": digest(path), "action": action}
            with archive_csvs(path) as (archive, names):
                for name in names:
                    with archive.open(name) as member, io.TextIOWrapper(member, encoding="utf-8-sig", newline="") as stream:
                        rows, statistics = sample_csv(stream, source, name)
                    samples.extend(rows)
                    report["files"].append({"file": name, **statistics})
        reports.append(report)
        save_json(storage / "source-audit.json", reports)
        notify({"phase": "source_prepared", "source": source["id"], "files": len(report["files"]),
                "skipped_files": len(report["skipped"])})
    return samples, reports


def pair_key(record):
    return stable_id(normalize(json.dumps(record["messages"][1:], ensure_ascii=False, sort_keys=True)))


def reading_text(values, fields=None):
    labels = {"pm25": ("PM2.5", "µg/m³"), "pm10": ("PM10", "µg/m³"),
              "temperature": ("nhiệt độ", "°C"), "humidity": ("độ ẩm", "%"), "noise": ("tiếng ồn", "dBA")}
    return ", ".join(f"{labels[field][0]} {values[field]:g} {labels[field][1]}" for field in (fields or labels) if field in values)


def concise(text):
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZĐ])", text)
    return " ".join(sentences[:2])


def dialogue_record(observation, variant, knowledge):
    values, source = observation["values"], observation["source"]
    preface = "Mẫu lịch sử được cung cấp: " + reading_text(values) + ". "
    documents = {doc["id"]: doc for doc in knowledge["documents"]}
    ids = [source]
    if source == "iscape_development":
        preface = "Mẫu thử nghiệm cảm biến trong quá khứ: " + reading_text(values) + ". "
        variant %= 4  # These are controlled tests, not representative ambient pollution.
    if variant == 0:
        fields = [field for field in ("pm25", "pm10") if field in values] or list(values)[:2]
        question = preface + "Đọc giúp mình " + ("số đo bụi thôi." if "pm25" in fields or "pm10" in fields else "hai chỉ số đầu thôi.")
        answer = reading_text(values, fields) + "."
    elif variant == 1:
        question = preface + "Mình chỉ muốn biết nhiệt độ và độ ẩm trong mẫu này."
        text = reading_text(values, ("temperature", "humidity"))
        answer = (text[0].upper() + text[1:] + ".") if text else "Mẫu này chưa có nhiệt độ và độ ẩm hợp lệ."
        missing = [name for field, name in (("temperature", "nhiệt độ"), ("humidity", "độ ẩm")) if field not in values]
        if text and missing:
            answer += " Mẫu này chưa có " + " và ".join(missing) + " hợp lệ."
    elif variant == 2:
        question = preface + "Có thể dùng mẫu này để kết luận không khí hiện tại ở Hà Nội không?"
        answer = "Chưa thể. Đây là mẫu lịch sử ở bối cảnh khác; để đánh giá Hà Nội lúc này cần dữ liệu đúng địa điểm và thời gian."
    elif variant == 3:
        question = preface + "Mẫu này có đủ cả PM2.5, PM10, nhiệt độ, độ ẩm và tiếng ồn không?"
        missing = [field for field in ALIASES if field not in values]
        names = {"pm25": "PM2.5", "pm10": "PM10", "temperature": "nhiệt độ", "humidity": "độ ẩm", "noise": "tiếng ồn"}
        answer = ("Mẫu này chưa có số đo hợp lệ cho " + ", ".join(names[field] for field in missing) + ". Cần bổ sung đúng phép đo; không điền bằng 0." if missing else
                  "Có, mẫu này có đủ năm chỉ số. Tuy nhiên, một mẫu đơn lẻ chưa mô tả được xu hướng theo thời gian hay đại diện cho cả khu vực.")
    elif variant == 4 and "pm25" in values:
        question = preface + "PM2.5 trong mẫu này có phải là AQI không?"
        answer = f"Không. {values['pm25']:g} µg/m³ là nồng độ PM2.5; AQI là chỉ số quy đổi theo cách tính và khoảng thời gian phù hợp. Không dùng trực tiếp con số này làm AQI."
        ids += ["airnow_aqi", "epa_pm"]
    elif variant == 5 and "noise" in values:
        question = preface + "Nếu gặp tiếng ồn như vậy và muốn giảm tiếp xúc, mình nên làm gì?"
        answer = concise(documents["noise_actions"]["answer"])
        ids += documents["noise_actions"]["source_ids"]
    elif variant == 6 and "humidity" in values and values["humidity"] > 60:
        question = preface + "Giả sử phòng mình có độ ẩm như vậy, làm sao hạn chế ẩm mốc?"
        answer = concise(documents["humidity_actions"]["answer"])
        ids += documents["humidity_actions"]["source_ids"]
    else:
        question = preface + "Mình muốn giảm bụi vào nhà thì nên bắt đầu thế nào?"
        answer = concise(documents["indoor_dust_actions"]["answer"])
        ids += documents["indoor_dust_actions"]["source_ids"]
    messages = [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]
    if variant == 7 and source != "iscape_development":
        messages.extend([{"role": "user", "content": "Mình chưa có máy lọc thì sao?"},
                         {"role": "assistant", "content": concise(documents["indoor_dust_actions"]["answer_without_filter"])}])
    return make_record(messages, "sensor_" + source, observation["group"], source_ids=sorted(set(ids)),
                       review="deterministic_sensor_values_and_source_checked_advice", historical=True,
                       observation={key: observation[key] for key in ("filename", "timestamp", "station", "channels", "key")},
                       measurement_values=values)


def prepare_dataset(samples, source_reports, destination, base_dir=None, per_source=40):
    """Isolated output: the live/pre-existing dataset and its split never change."""
    destination = Path(destination)
    base_dir = Path(base_dir) if base_dir is not None else ROOT / "data/xanhnon"
    knowledge = json.loads((base_dir / "knowledge.json").read_text(encoding="utf-8"))
    base = {split: [json.loads(line) for line in (base_dir / f"{split}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            for split in ("train", "validation")}
    seen_pairs = {pair_key(row) for rows in base.values() for row in rows}
    seen_vectors, seen_origins, skipped, generated = set(), set(), Counter(), {"train": [], "validation": []}
    skipped_sources = []
    by_source = defaultdict(list)
    # Source priority and complete vectors win over inferior copies.
    priority = {source["id"]: source["priority"] for source in SOURCES}
    for sample in sorted(samples, key=lambda row: (-len(row["values"]), "processed" not in row["filename"].lower(), priority[row["source"]], row["key"])):
        origin = (file_family(sample["filename"]), sample.get("timestamp")) if sample.get("timestamp") else None
        if origin and origin in seen_origins:
            skipped["duplicate_or_inferior_copy_of_same_observation"] += 1
            continue
        if sample["key"] in seen_vectors:
            skipped["duplicate_measurement_vector"] += 1
            continue
        seen_vectors.add(sample["key"])
        if origin:
            seen_origins.add(origin)
        by_source[sample["source"]].append(sample)
    for source in SOURCES:
        rows = by_source[source["id"]]
        groups = sorted({row["group"] for row in rows}, key=stable_id)
        if len(groups) < 2:
            skipped_sources.append({"source": source["id"], "reason": "all_duplicate_or_no_independent_recordings", "remaining_recordings": len(groups)})
            continue
        validation_groups = set(groups[:max(1, round(len(groups) * 0.2))])
        buckets = {"train": [], "validation": []}
        for row in rows:
            buckets["validation" if row["group"] in validation_groups else "train"].append(row)
        for split, candidates in buckets.items():
            random.Random(42).shuffle(candidates)
            target = max(1, round(per_source * 0.2)) if split == "validation" else per_source - max(1, round(per_source * 0.2))
            selected, diversity = 0, Counter()
            for index, observation in enumerate(candidates):
                values = observation["values"]
                signature = tuple((field, round(value / (10 if field in ("pm25", "pm10", "humidity", "noise") else 5))) for field, value in sorted(values.items()))
                if diversity[signature] >= 2:
                    skipped["near_identical_scenario"] += 1
                    continue
                record = dialogue_record(observation, index % 8, knowledge)
                key = pair_key(record)
                if key in seen_pairs:
                    skipped["existing_or_duplicate_dialogue"] += 1
                    continue
                seen_pairs.add(key)
                diversity[signature] += 1
                generated[split].append(record)
                selected += 1
                if selected >= target:
                    break
            if selected == 0:
                raise ValueError("No new usable examples for " + source["id"] + "/" + split)
    sensor_counts = {split: dict(Counter(row["source"] for row in rows)) for split, rows in generated.items()}
    # Rehearse existing communication/advice skills without retraining the whole corpus.
    replay = {"train": {"environment_style": 48, "environment_advice": 16}, "validation": {}}
    for source in sorted({row["source"] for row in base["validation"]}):
        replay["validation"][source] = 4
    for split, limits in replay.items():
        for source, count in limits.items():
            candidates = sorted((row for row in base[split] if row["source"] == source), key=lambda row: row["id"])
            generated[split].extend(candidates[:count])
    artifacts = {}
    destination.mkdir(parents=True, exist_ok=True)
    for split, rows in generated.items():
        random.Random(42).shuffle(rows)
        target = destination / f"{split}.jsonl"
        target.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        artifacts[target.name] = digest(target)
    train_groups = {row["group_id"] for row in generated["train"]}
    if train_groups & {row["group_id"] for row in generated["validation"]}:
        raise ValueError("Sensor preparation leaked recording groups between train and validation")
    manifest = {"schema_version": 1, "built_at": datetime.now(timezone.utc).isoformat(), "seed": 42,
                "sources": [{key: value for key, value in report.items() if key not in ("files", "skipped")} for report in source_reports],
                "counts": {split: dict(Counter(row["source"] for row in rows)) for split, rows in generated.items()},
                "new_sensor_counts": sensor_counts, "skipped_sources": skipped_sources,
                "deduplication": dict(skipped), "artifacts_sha256": artifacts,
                "environment_sources": knowledge["sources"], "knowledge_sha256": digest(base_dir / "knowledge.json"),
                "required_train_sources": sorted(sensor_counts["train"]),
                "total_rows": sum(len(rows) for rows in generated.values()),
                "base_manifest_sha256": digest(base_dir / "manifest.json"),
                "limitations": ["Bounded samples, not every row of the four datasets.",
                                "Dialogue templates teach reading supplied historical values; no live or forecast facts are learned.",
                                "Controlled sensor-development tests are not representative outdoor air-quality observations.",
                                "No AQI label is invented from an isolated PM reading; missing noise/RH are not imputed.",
                                "Validation holds out recording files but still uses the same templates; it is not independent expert assessment.",
                                "Author-processed files are preferred if usable; this is not a claim that every sensor is calibrated."]}
    save_json(destination / "manifest.json", manifest)
    notice = "# Sensor sources for Xanh Non\n\n" + "\n".join(f"- {row['title']}: {row['url']} (license: {row.get('license', 'see metadata')})" for row in source_reports)
    notice += "\n\nDerived Vietnamese dialogue templates; sampled, filtered, deduplicated, grouped by recording. Original measurements are historical. Official advice sources are inherited from data/xanhnon/knowledge.json.\n"
    notice += "\n## Existing examples used for rehearsal\n\n" + (base_dir / "NOTICE.md").read_text(encoding="utf-8")
    (destination / "NOTICE.md").write_text(notice, encoding="utf-8")
    shutil.copyfile(base_dir / "LICENSE-APACHE-2.0.txt", destination / "LICENSE-APACHE-2.0.txt")
    return manifest
