"""Read-only local monitoring for the current sensor-training queue.

Checks every 30 seconds, records changes only, and stops when this job finishes.
Does not call an LLM, activate models, or restart/duplicate training jobs.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import time

import psutil

from queue_sensor_training import TERMINAL
from sensor_training_data import save_json
from training_state import training_in_progress


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def verified_worker(job):
    try:
        process = psutil.Process(job["worker_pid"])
        if (abs(process.create_time() - job["worker_create_time"]) < 0.1 and process.is_running()
                and any(Path(arg).name in {"queue_sensor_training.py", "recover_xanhnon_training.py", "run_xanhnon_4b_cycle.py"}
                        for arg in process.cmdline())):
            return process
    except (psutil.Error, KeyError, ValueError, TypeError):
        pass
    return None


def snapshot(storage):
    storage = Path(storage)
    job = read_json(storage / "sensor-queue.json")
    current = read_json(storage / 'current-training.json')
    if current.get('cycle_state'):
        cycle_path = Path(current['cycle_state']).resolve()
        if not cycle_path.is_relative_to(storage.resolve()):
            raise ValueError('Current training state must belong to this storage')
        cycle = read_json(cycle_path)
        if cycle:
            job = {**cycle, 'worker_create_time':current['worker_create_time'],
                   'source':current.get('source','Qwen3-4B corrective LoRA'),
                   'status':'training' if cycle['status']=='running' else cycle['status']}
    worker = verified_worker(job)
    owned = [worker] if worker else []
    if worker:
        try:
            owned += worker.children(recursive=True)
        except psutil.Error:
            pass
    cpu, io_bytes = 0.0, 0
    for process in owned:
        try:
            cpu += sum(process.cpu_times()[:2])
            counters = process.io_counters()
            io_bytes += counters.read_bytes + counters.write_bytes
        except psutil.Error:
            pass
    candidate = Path(job["candidate"]) if job.get("candidate") else None
    progress = read_json(candidate / "progress.json") if candidate else {}
    report = read_json(candidate / "training_report.json") if candidate else {}
    planned = progress.get("steps_planned", report.get("steps"))
    phase = job.get("phase")
    review = {}
    if job.get('review_state'):
        review_path = Path(job['review_state']).resolve()
        if not review_path.is_relative_to(storage.resolve()):
            raise ValueError('Answer review state must belong to this storage')
        review = read_json(review_path)
    if job.get("status") == "training" and progress and phase != 'answer_evaluation':
        configuration = progress.get("configuration", {})
        if planned is None and progress.get("data", {}).get("train", {}).get("encoded_rows"):
            planned = math.ceil(progress["data"]["train"]["encoded_rows"] * configuration.get("epochs", 1) / configuration.get("accumulation", 4))
            if configuration.get("max_steps"):
                planned = min(planned, configuration["max_steps"])
        if progress.get('phase') == 'loading_model':
            phase = 'loading_model'
        elif progress.get("recovery") and progress.get("resume_checkpoint_validation_loss") is None:
            phase = "checkpoint_validation"
        elif not progress.get("steps_completed") and progress.get("baseline_validation_loss") is None:
            phase = "baseline_validation"
        elif planned and progress.get("steps_completed", 0) >= planned:
            phase = "final_validation_or_saving"
        else:
            phase = "updating_adapter"
    cache = storage / "sensor-sources"
    files, byte_count, partials = 0, 0, []
    for path in cache.rglob("*"):
        try:
            if path.is_file() and path.suffix in (".csv", ".zip", ".download"):
                byte_count += path.stat().st_size
                if path.suffix == ".download":
                    partials.append(path.name)
                else:
                    files += 1
        except FileNotFoundError:
            pass  # A completed download may be atomically renamed during this read.
    terminal = job.get("status") in TERMINAL | {'awaiting_manual_review', 'rejected_answer_review'}
    attention = job.get("status") in ("failed", "incomplete") or (not worker and not terminal)
    if job.get('status') == 'awaiting_manual_review':
        attention = True
    if terminal and job.get("status") in ("awaiting_answer_evaluation", "rejected_validation"):
        attention = not bool(report.get("selected_data_pass_completed"))
    return {"checked_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
            "queue_status": job.get("status", "missing_queue"), "phase": phase,
            "source": job.get("source"), "worker_alive": bool(worker),
            "trainer_running": training_in_progress(), "needs_attention": attention,
            "error": job.get("error"), "terminal": terminal,
            "candidate": str(candidate) if candidate else None,
            "steps_completed": progress.get("steps_completed", report.get("steps_completed", 0)),
            "steps_planned": planned,
            "baseline_validation_loss": report.get("baseline_validation_loss"),
            "candidate_validation_loss": report.get("candidate_validation_loss"),
            'review_status':review.get('status'),'review_variant':review.get('phase'),
            'review_completed_cases':review.get('completed_cases'),
            "cached_files": files, "cached_mb": round(byte_count / 2**20, 1), "downloading": partials,
            "owned_cpu_seconds": round(cpu, 2), "owned_io_bytes": io_bytes,
            "data_counts": job.get("data_counts"), "deduplication": job.get("deduplication"),
            "skipped_sources": job.get("skipped_sources"), "model_activated": False}


def watch(storage, interval=30, max_hours=8):
    storage = Path(storage)
    storage.mkdir(parents=True, exist_ok=True)
    with (storage / "training-monitor.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                return
        else:
            import fcntl
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
        started, last_activity = time.monotonic(), time.monotonic()
        previous_activity = previous_event = None
        with (storage / "training-monitor-events.jsonl").open("a", encoding="utf-8", buffering=1) as log:
            while True:
                try:
                    current = snapshot(storage)
                    activity = tuple(current[key] for key in ("owned_cpu_seconds", "owned_io_bytes", "cached_mb", "steps_completed", "queue_status", "source"))
                    if activity != previous_activity:
                        last_activity = time.monotonic()
                    current["stalled"] = not current["terminal"] and time.monotonic() - last_activity > 15 * 60
                    current["needs_attention"] |= current["stalled"]
                    event = tuple(current[key] for key in ("queue_status", "phase", "source", "steps_completed", "needs_attention", "error"))
                    current["monitor_pid"] = os.getpid()
                    current["monitor_create_time"] = psutil.Process().create_time()
                    save_json(storage / "training-monitor-status.json", current)
                    if event != previous_event:
                        log.write(json.dumps(current, ensure_ascii=False) + "\n")
                    previous_event, previous_activity = event, activity
                    if current["terminal"]:
                        return
                    if time.monotonic() - started > max_hours * 3600:
                        current.update({"needs_attention": True, "monitor_limit_reached": True})
                        save_json(storage / "training-monitor-status.json", current)
                        log.write(json.dumps(current, ensure_ascii=False) + "\n")
                        return
                except (OSError, ValueError) as exc:
                    # Preserve monitoring across transient reads without masking the error.
                    log.write(json.dumps({"checked_at": datetime.now(timezone.utc).isoformat(), "monitor_read_error": str(exc)}) + "\n")
                time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, default=Path("D:/XanhNon-auto-training"))
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--max-hours", type=int, default=8)
    args = parser.parse_args()
    if args.interval < 5 or args.max_hours < 1:
        parser.error("Interval must be at least 5 seconds and max-hours positive")
    watch(args.storage, args.interval, args.max_hours)
