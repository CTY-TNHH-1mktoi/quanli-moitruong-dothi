"""Scheduled local LoRA updates from changed, prepared data; never replace live weights."""

import argparse
from datetime import datetime, timezone
import json
import math
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

import psutil

from model_release import read_release
from training_state import training_in_progress
from feedback_training_data import prepare_feedback_dataset, fingerprint as prepared_fingerprint
from chat_learning import ConversationLearner


ROOT = Path(__file__).resolve().parent
DEFAULT_STORAGE = Path("D:/XanhNon-auto-training")
STATE = ROOT / ".runtime/xanhnon-training/automatic-state.json"


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".new")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def dataset_fingerprint():
    return prepared_fingerprint(ROOT / "data/xanhnon")


def candidate_status(report):
    before, after = report.get("baseline_validation_loss"), report.get("candidate_validation_loss")
    if (report.get("steps", 0) <= 0 or not report.get("selected_data_pass_completed")
            or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                   for value in (before, after))):
        return "incomplete"
    return "awaiting_answer_evaluation" if after < before else "rejected_validation"


def memory_ready(allow_cpu_paging=False):
    available = psutil.virtual_memory().available
    return available >= 3 * 2**30 or (
        allow_cpu_paging and available + psutil.swap_memory().free >= 6 * 2**30)


def training_seed(release, root=ROOT):
    """Continue a real adapter, or start fresh LoRA on the verified recovered merge."""
    if release.get('adapter'):
        return ['--adapter',str(release['adapter'])]
    base=Path(root)/'models/xanhnon-style-v2-training-base'
    proof=base/'recovery-training-base.json'
    weights=base/'model.safetensors'
    if not proof.is_file() or not weights.is_file() or not (base/'config.json').is_file():
        raise ValueError('A standalone adapter or verified recovered training base is required')
    expected=json.loads(proof.read_text(encoding='utf-8'))['sha256']
    digest=hashlib.sha256()
    with weights.open('rb') as handle:
        for block in iter(lambda:handle.read(4*1024*1024),b''):digest.update(block)
    if digest.hexdigest()!=expected:
        raise ValueError('Recovered training checkpoint checksum mismatch')
    return ['--model',str(base)]


def run_training(command, output, timeout_seconds=3 * 60 * 60):
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError('Training timeout must be a positive finite duration')
    process = subprocess.Popen(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    try:
        return process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        # A Windows venv launcher may have a child interpreter: stop our whole job.
        try:
            owned = psutil.Process(process.pid)
            children = owned.children(recursive=True)
            for child in reversed(children):
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            owned.terminate()
            _, alive = psutil.wait_procs(children + [owned], timeout=5)
            for child in alive:
                child.kill()
        except psutil.NoSuchProcess:
            pass
        process.wait(timeout=5)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, default=DEFAULT_STORAGE)
    parser.add_argument("--check", action="store_true", help="Readiness check without starting training")
    parser.add_argument("--allow-cpu-paging", action="store_true",
                        help="Explicitly allow this run to use paging with at least 6 GiB RAM+swap available")
    args = parser.parse_args()
    storage = args.storage.resolve()
    storage.mkdir(parents=True, exist_ok=True)
    with (storage / "automatic.log").open("a", encoding="utf-8", buffering=1) as log:
        # pythonw from Task Scheduler has no console; all output stays in a log.
        if sys.stdout is None:
            sys.stdout = log
        if sys.stderr is None:
            sys.stderr = log
        fingerprint = dataset_fingerprint()
        previous = json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else {}
        result = {"checked_at": datetime.now(timezone.utc).isoformat(), "fingerprint": fingerprint,
                  "model_activated": False, "storage": str(storage)}
        queue_path = storage / "sensor-queue.json"
        pending_sensor_queue = queue_path.is_file() and json.loads(queue_path.read_text(encoding="utf-8")).get("status") not in {
            "awaiting_answer_evaluation", "rejected_validation", "incomplete", "failed", "skipped_no_new_data"}
        data_dir = ROOT / "data/xanhnon"
        learner = ConversationLearner(ROOT / ".runtime/xanhnon-learning/questions.sqlite3", base_dir=data_dir)
        if os.getenv("XANHNON_LEARNING_DB"):
            learner = ConversationLearner(base_dir=data_dir)
        if not args.check:
            learner.recheck()
        result["learning"] = learner.stats()
        if not training_in_progress() and not pending_sensor_queue:
            automatic = learner.training_records()
            if automatic:
                data_dir, fingerprint, feedback = prepare_feedback_dataset(data_dir, storage, learned_records=automatic)
            else:
                data_dir, fingerprint, feedback = prepare_feedback_dataset(data_dir, storage)
            result.update(fingerprint=fingerprint, feedback=feedback, data_dir=str(data_dir))
        if training_in_progress():
            result["status"] = "skipped_training_in_progress"
        elif pending_sensor_queue:
            result["status"] = "skipped_pending_sensor_queue"
        elif previous.get("trained_fingerprint") == fingerprint:
            result["status"] = "skipped_unchanged_data"
        elif previous.get("failed_date") == datetime.now().date().isoformat() and previous.get("failed_fingerprint") == fingerprint:
            result["status"] = "waiting_until_next_day_after_failure"
        elif shutil.disk_usage(storage).free < 4 * 2**30 or shutil.disk_usage(ROOT).free < 3 * 2**30:
            result["status"] = "waiting_for_disk_space"
        elif not memory_ready(args.allow_cpu_paging):
            result["status"] = "waiting_for_memory"
        else:
            release = read_release(ROOT)
            seed=training_seed(release)
            candidate = storage / datetime.now().strftime("candidate-%Y%m%d-%H%M%S")
            command = [str(ROOT / ".venv/Scripts/python.exe"), str(ROOT / "train_xanhnon.py"),
                       "--train", "--output", str(candidate), *seed,
                       "--max-length", "1536", "--epochs", "1", "--limit", "128",
                       "--validation-limit", "24", "--last-layers", "8", "--threads", "2",
                       "--learning-rate", "0.0001", "--checkpoint-every", "8"]
            if data_dir != ROOT / "data/xanhnon":
                command.extend(["--data-dir", str(data_dir)])
                manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
                for source in manifest["required_train_sources"]:
                    command.extend(["--train-source", source])
            if args.allow_cpu_paging:
                command.append("--allow-cpu-paging")
            result.update({"status": "ready", "candidate": str(candidate), "command": command})
            if not args.check:
                result["status"] = "training"
                save(STATE, {**previous, **result})
                save(storage / "latest-status.json", result)
                with (storage / "training.log").open("a", encoding="utf-8") as output:
                    try:
                        returncode = run_training(command, output)
                        if returncode:
                            raise RuntimeError(f"Training exited with status {returncode}")
                        report = json.loads((candidate / "training_report.json").read_text(encoding="utf-8"))
                        result.update({"status": candidate_status(report), "steps": report.get("steps"),
                                       "baseline_validation_loss": report.get("baseline_validation_loss"),
                                       "candidate_validation_loss": report.get("candidate_validation_loss")})
                        if result["status"] != "incomplete":
                            result["trained_fingerprint"] = fingerprint
                    except (subprocess.TimeoutExpired, OSError, ValueError, RuntimeError) as exc:
                        # Retry failed data only on the next day; avoid endless hourly training failures.
                        result.update({"status": "failed", "error": str(exc), "failed_date": datetime.now().date().isoformat(),
                                       "failed_fingerprint": fingerprint})
        if not args.check:
            save(STATE, {**previous, **result})
        print(json.dumps(result, ensure_ascii=False), flush=True)
        log.write(json.dumps(result, ensure_ascii=False) + "\n")
        if not args.check:
            save(storage / "latest-status.json", result)


if __name__ == "__main__":
    main()
