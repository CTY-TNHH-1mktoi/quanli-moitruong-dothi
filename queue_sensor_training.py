"""Run one persisted four-source Xanh Non training job after the current job.

Uses local resources only. Original data, active release, and weights are preserved.
"""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback

import psutil

from daily_train_xanhnon import candidate_status, memory_ready, run_training
from model_release import read_release
from sensor_training_data import SOURCES, collect_sources, digest, prepare_dataset, save_json
from training_state import training_in_progress


ROOT = Path(__file__).resolve().parent
STORAGE = Path("D:/XanhNon-auto-training")
TERMINAL = {"awaiting_answer_evaluation", "rejected_validation", "incomplete", "failed", "skipped_no_new_data"}


def dependency_ready(directory):
    directory = Path(directory)
    path = directory / "training_report.json"
    if not path.is_file():
        return False
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("mode") != "lora_candidate" or not report.get("selected_data_pass_completed"):
        raise RuntimeError("Previous training did not complete its selected-data pass")
    return not training_in_progress()


def source_adapter(dependency, active):
    """Continue a complete improved candidate; retain the active baseline otherwise."""
    report = json.loads((Path(dependency) / "training_report.json").read_text(encoding="utf-8"))
    if candidate_status(report) == "awaiting_answer_evaluation":
        if not (Path(dependency) / "adapter_model.safetensors").is_file():
            raise ValueError("Previous candidate is missing its adapter")
        return Path(dependency), "continued_previous_candidate_after_validation_loss_improved"
    return Path(active), "previous_candidate_not_better_on_validation_using_active_adapter"


def queue_pending(storage):
    path = Path(storage) / "sensor-queue.json"
    if not path.is_file():
        return False
    return json.loads(path.read_text(encoding="utf-8")).get("status") not in TERMINAL


def validate_prepared_dataset(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    for filename in ("train.jsonl", "validation.jsonl"):
        if digest(directory / filename) != manifest["artifacts_sha256"][filename]:
            raise ValueError("Prepared dataset changed since its manifest: " + filename)
    configuration = prepared_training_configuration(manifest)
    if configuration.get('capacity_adapter'):
        from expand_xanhnon_adapter import verify_expansion
        verify_expansion(configuration['capacity_adapter'], read_release(ROOT)['adapter'],
                         configuration['capacity_adapter_manifest_sha256'])
    return manifest


def prepared_training_configuration(manifest):
    configuration = {"max_length": 512, "epochs": 1, "learning_rate": 0.00005,
                     "start_from_active_release": False, 'capacity_adapter': None,
                     'capacity_adapter_manifest_sha256': None}
    supplied = manifest.get("training_configuration", {})
    if not isinstance(supplied, dict) or set(supplied) - set(configuration):
        raise ValueError("Unsupported prepared training configuration")
    configuration.update(supplied)
    for key, minimum, maximum in (("max_length", 128, 2048), ("epochs", 1, 3)):
        value = configuration[key]
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError("Invalid prepared training " + key)
    rate = configuration["learning_rate"]
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or not 0 < rate <= 0.001:
        raise ValueError("Invalid prepared training learning_rate")
    if not isinstance(configuration["start_from_active_release"], bool):
        raise ValueError("Invalid prepared training start_from_active_release")
    directory, fingerprint = configuration['capacity_adapter'], configuration['capacity_adapter_manifest_sha256']
    if directory is not None or fingerprint is not None:
        if (not isinstance(directory, str) or not Path(directory).is_absolute()
                or not isinstance(fingerprint, str) or len(fingerprint) != 64
                or any(c not in '0123456789abcdef' for c in fingerprint)
                or not configuration['start_from_active_release']):
            raise ValueError('Invalid explicit active-adapter capacity experiment')
    return configuration


def training_command(data_dir, candidate, adapter, job):
    return [str(ROOT / ".venv/Scripts/python.exe"), str(ROOT / "train_xanhnon.py"),
            "--train", "--data-dir", str(data_dir), "--output", str(candidate),
            "--adapter", str(adapter), "--epochs", str(job.get("epochs", 1)),
            "--max-length", str(job.get("max_length", 512)), "--last-layers", "8",
            "--threads", "2", "--checkpoint-every", "8", "--learning-rate",
            str(job.get("learning_rate", 0.0001)), "--allow-cpu-paging"]


def choose_training_adapter(job, active):
    if job.get('capacity_adapter'):
        from expand_xanhnon_adapter import verify_expansion
        verify_expansion(job['capacity_adapter'], active, job['capacity_adapter_manifest_sha256'])
        return Path(job['capacity_adapter']), 'expanded_active_adapter_capacity_experiment'
    if job.get("start_from_active_release"):
        return Path(active), "explicit_reviewed_reset_to_active_release"
    return source_adapter(job["after"], active)


def enqueue(storage, dependency, prepared=None):
    storage, dependency = Path(storage).resolve(), Path(dependency).resolve()
    prepared = Path(prepared).resolve() if prepared else None
    prepared_manifest = validate_prepared_dataset(prepared) if prepared else None
    if not dependency.is_dir() or not ((dependency / "progress.json").is_file() or (dependency / "training_report.json").is_file()):
        raise ValueError("Choose an actual current/completed training candidate as the dependency")
    path = storage / "sensor-queue.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    if previous:
        if (previous.get("after") == str(dependency) and previous.get("prepared_data_dir") == (str(prepared) if prepared else None)
                and previous.get("status") != "failed"):
            return previous  # Repeated requests do not enqueue duplicate training.
        if previous.get("status") not in TERMINAL:
            raise RuntimeError("An unfinished sensor training job is already queued")
        archive = storage / ("sensor-queue-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".json")
        save_json(archive, previous)
    job = {"version": 1, "requested_at": datetime.now(timezone.utc).isoformat(),
           "status": "waiting_for_previous", "after": str(dependency),
           "sources": [{key: source[key] for key in ("id", "title", "url")} for source in SOURCES],
           "deduplicate": True, "prefer_usable_author_processed": True,
           "examples_per_source_limit": 40, "model_activated": False,
           "purpose": "Read supplied historical measurements, short source-backed consultation, follow-up context; not forecasting",
           "allow_cpu_paging": True}
    if prepared:
        configuration = prepared_training_configuration(prepared_manifest)
        job.update({"prepared_data_dir": str(prepared), "prepared_manifest_sha256": digest(prepared / "manifest.json"),
                    "stage": "dialogue_correction", **configuration,
                    "purpose": "Correct reviewed factual/context errors and rehearse earlier sensor/dialogue skills",
                    "sources": prepared_manifest.get("sources", []) + prepared_manifest.get("rehearsal_sources", []),
                    "topics": prepared_manifest.get("required_train_topics", [])})
        job.pop("examples_per_source_limit", None)
    save_json(path, job)
    return job


def work(storage):
    storage = Path(storage).resolve()
    path = storage / "sensor-queue.json"
    # An OS lock is released if the worker exits; only one worker can own this job.
    with (storage / "sensor-queue.lock").open("a+b") as lock:
        if os.name == "nt":
            import msvcrt
            lock.seek(0)
            lock.write(b"0")
            lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                return {"status": "worker_already_running"}
        else:
            import fcntl
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {"status": "worker_already_running"}
        job = json.loads(path.read_text(encoding="utf-8"))
        if job.get("status") in TERMINAL:
            return job
        job.update({"worker_pid": os.getpid(), "worker_create_time": psutil.Process().create_time()})

        def update(**values):
            job.update(values)
            job["updated_at"] = datetime.now(timezone.utc).isoformat()
            save_json(path, job)

        try:
            update(status="waiting_for_previous")
            deadline = time.monotonic() + 4 * 3600
            while not dependency_ready(job["after"]):
                if not training_in_progress():
                    raise RuntimeError("Previous training stopped without a complete report; queued training has not started")
                if time.monotonic() > deadline:
                    raise TimeoutError("Timed out waiting for previous training")
                time.sleep(30)
            if job.get("prepared_data_dir"):
                update(status="preparing_dialogues", phase="validating_prepared_dialogues")
                data_dir = Path(job["prepared_data_dir"])
                manifest = validate_prepared_dataset(data_dir)
                if digest(data_dir / "manifest.json") != job["prepared_manifest_sha256"]:
                    raise ValueError("Prepared dialogue manifest changed after enqueue")
            else:
                update(status="preparing_sources")
                samples, reports = collect_sources(storage / "sensor-sources", lambda value: update(**value))
                data_dir = storage / "sensor-dataset"
                update(status="preparing_dialogues", phase="filtering_deduplicating_and_splitting")
                manifest = prepare_dataset(samples, reports, data_dir, per_source=job["examples_per_source_limit"])
            update(data_counts=manifest["counts"], skipped_sources=manifest["skipped_sources"],
                   deduplication=manifest["deduplication"], data_dir=str(data_dir))
            new_examples = manifest.get("new_dialogue_counts", {}).get("train")
            if new_examples is None:
                new_examples = sum(manifest.get("new_sensor_counts", {}).get("train", {}).values())
            if not new_examples and not job.get('capacity_adapter'):
                update(status="skipped_no_new_data", phase="all_available_examples_already_covered_or_unsuitable")
                return job
            fingerprint = digest(data_dir / "train.jsonl") + ":" + digest(data_dir / "validation.jsonl")
            if job.get('capacity_adapter'):
                # An explicit, verified architecture experiment can reuse frozen
                # data once. Subsequent identical experiment requests still skip.
                configuration = prepared_training_configuration(manifest)
                import hashlib
                fingerprint += ':capacity:' + hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
            trained = storage / "sensor-trained-fingerprints.json"
            prior = json.loads(trained.read_text(encoding="utf-8")) if trained.is_file() else []
            if fingerprint in prior:
                update(status="skipped_no_new_data", data_dir=str(data_dir), fingerprint=fingerprint)
                return job
            active_adapter = read_release(ROOT)["adapter"]
            adapter, reason = choose_training_adapter(job, active_adapter)
            prefix = "dialogue-candidate-" if job.get("prepared_data_dir") else "sensor-candidate-"
            candidate = storage / datetime.now().strftime(prefix + "%Y%m%d-%H%M%S")
            command = training_command(data_dir, candidate, adapter, job)
            update(status="waiting_for_resources", data_dir=str(data_dir), candidate=str(candidate),
                   source_adapter=str(adapter), adapter_reason=reason, command=command,
                   data_counts=manifest["counts"], deduplication=manifest["deduplication"], fingerprint=fingerprint)
            deadline = time.monotonic() + 4 * 3600
            while training_in_progress() or not memory_ready(allow_cpu_paging=True):
                if time.monotonic() > deadline:
                    raise TimeoutError("Timed out waiting for local training resources")
                time.sleep(30)
            update(status="training", phase="trainer_starting")
            with (storage / "sensor-training.log").open("a", encoding="utf-8") as log:
                result = run_training(command, log, timeout_seconds=24 * 60 * 60)
            if result:
                raise RuntimeError("Sensor dialogue training exited with status " + str(result))
            report_path = candidate / "training_report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            status = candidate_status(report)
            if status != "incomplete":
                save_json(trained, prior + [fingerprint])
            update(status=status, phase="training_finished", report=str(report_path),
                   steps=report.get("steps"), trained_examples=report.get("trained_examples"),
                   baseline_validation_loss=report.get("baseline_validation_loss"),
                   candidate_validation_loss=report.get("candidate_validation_loss"))
        except Exception as exc:
            update(status="failed", error=str(exc))
            with (storage / "sensor-queue-errors.log").open("a", encoding="utf-8") as log:
                traceback.print_exc(file=log)
        return job


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, default=STORAGE)
    parser.add_argument("--enqueue-after", type=Path, help="Persist a job waiting for this actual training candidate")
    parser.add_argument("--prepared-data", type=Path, help="Use this verified prepared batch rather than downloading sensor sources")
    parser.add_argument("--work", action="store_true", help="Run/resume the pending job")
    args = parser.parse_args()
    args.storage.mkdir(parents=True, exist_ok=True)
    if args.enqueue_after:
        result = enqueue(args.storage, args.enqueue_after, args.prepared_data)
    elif args.work:
        result = work(args.storage)
    else:
        result = json.loads((args.storage / "sensor-queue.json").read_text(encoding="utf-8"))
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
