"""Keep the dashboard available without starting a second model during training."""

import atexit
import json
import os
from pathlib import Path


STATE_PATH = Path(__file__).resolve().parent / ".runtime/xanhnon-training/active.json"


def training_in_progress():
    try:
        import psutil
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        process = psutil.Process(int(state["pid"]))
        return (process.is_running() and abs(process.create_time() - state["create_time"]) < 0.1
                and any(Path(argument).name == "train_xanhnon.py" for argument in process.cmdline()))
    except (OSError, ValueError, KeyError, TypeError):
        return False
    except Exception:
        # A process can exit between reading the marker and querying its PID.
        return False


def register_training(pid, output):
    import psutil
    if training_in_progress():
        previous = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if previous["pid"] != pid:
            raise RuntimeError("Another Xanh Non training process is already active")
    state = {"pid": pid, "create_time": psutil.Process(pid).create_time(), "output": str(output)}
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
    if pid == os.getpid():
        def clear():
            try:
                current = json.loads(STATE_PATH.read_text(encoding="utf-8"))
                if current["pid"] == pid and current["create_time"] == state["create_time"]:
                    STATE_PATH.unlink(missing_ok=True)
            except (OSError, ValueError, KeyError):
                pass
        atexit.register(clear)
