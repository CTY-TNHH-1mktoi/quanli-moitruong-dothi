"""Build immutable snapshots from reviewed feedback and source-checked questions."""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from chat_feedback import FeedbackStore
from prepare_xanhnon_data import make_record, normalize
from chat_learning import SOURCE as LEARNING_SOURCE


SOURCE = "environment_feedback"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(data_dir):
    data_dir = Path(data_dir)
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    hashes = manifest["artifacts_sha256"]
    for name in ("train.jsonl", "validation.jsonl"):
        if digest(data_dir / name) != hashes[name]:
            raise ValueError("Dataset differs from its prepared manifest")
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


def _records(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _pairs(record):
    messages = record["messages"]
    return {(normalize(messages[index - 1]["content"]), normalize(message["content"]))
            for index, message in enumerate(messages) if message["role"] == "assistant" and index > 0}


def _prompt(record):
    return tuple((turn["role"], normalize(turn["content"])) for turn in record["messages"][:-1]
                 if turn["role"] != "system")


def prepare_feedback_dataset(base_dir, storage, store=None, learned_records=()):
    """Pending votes and unsupported questions cannot change training input."""
    base_dir, storage = Path(base_dir).resolve(), Path(storage).resolve()
    base_fingerprint = fingerprint(base_dir)
    store = store or FeedbackStore()
    approved = store.list("approved", limit=None)
    learned_records = list(learned_records)
    if not approved and not learned_records:
        return base_dir, base_fingerprint, {"approved": 0, "included": 0, "skipped": {}}
    training_prompts, heldout = set(), set()
    for name in ("train", "validation", "test"):
        path = base_dir / f"{name}.jsonl"
        if path.is_file():
            for record in _records(path):
                if name == "train":
                    training_prompts.add(_prompt(record))
                else:
                    heldout.update(question for question, _ in _pairs(record))
    evaluation = base_dir / "eval_consultation.json"
    if evaluation.is_file():
        for case in json.loads(evaluation.read_text(encoding="utf-8")):
            heldout.add(normalize(case["question"]))
            heldout.update(normalize(turn["content"]) for turn in case.get("history", []) if turn["role"] == "user")
    additions, skipped = [], Counter()
    for row in approved:
        review = row["review"]
        if not review or not review.get("privacy_reviewed") or not review.get("facts_reviewed"):
            skipped["unreviewed"] += 1
            continue
        record = make_record(review["messages"], SOURCE, str(row["id"]),
            source_ids=review["source_ids"], review="locally_reviewed_feedback",
            feedback_id=row["id"], data_policy=review["data_policy"],
            supervise_last_assistant_only=True)
        # A shared question alone also leaks the holdout into training, even when
        # its suggested answer differs. Check all reviewed context turns too.
        if _prompt(record) in training_prompts or {question for question, _ in _pairs(record)} & heldout:
            skipped["duplicate_or_holdout_question"] += 1
            continue
        training_prompts.add(_prompt(record))
        additions.append(record)
    for record in learned_records:
        if record.get("source") != LEARNING_SOURCE or record.get("review") != "automatic_existing_verified_source":
            raise ValueError("Automatic training input must come from the verified question learner")
        original = {normalize(record.get("original_question", "")), normalize(record.get("context_user", ""))}
        if _prompt(record) in training_prompts or ({question for question, _ in _pairs(record)} | original) & heldout:
            skipped["duplicate_or_holdout_question"] += 1
            continue
        training_prompts.add(_prompt(record))
        additions.append(record)
    summary = {"approved": len(approved), "automatic_available": len(learned_records),
               "included": len(additions), "skipped": dict(skipped),
               "sources": dict(Counter(record["source"] for record in additions))}
    if not additions:
        return base_dir, base_fingerprint, summary
    serialized = json.dumps(additions, ensure_ascii=False, sort_keys=True)
    combined = hashlib.sha256((base_fingerprint + serialized).encode("utf-8")).hexdigest()
    destination = storage / "feedback-data" / combined
    if destination.is_dir():
        return destination, fingerprint(destination), summary
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((base_dir / "manifest.json").read_text(encoding="utf-8"))
    # Build beside the final directory and rename only when every hash is ready.
    with tempfile.TemporaryDirectory(prefix="prepare-", dir=destination.parent) as temporary:
        work = Path(temporary) / "data"
        work.mkdir()
        for name, expected in manifest["artifacts_sha256"].items():
            source = (base_dir / name).resolve()
            if source.parent != base_dir or digest(source) != expected:
                raise ValueError("Invalid base artifact")
            shutil.copyfile(source, work / name)
        path = work / "train.jsonl"
        with path.open("a", encoding="utf-8") as output:
            output.write("\n" + "\n".join(json.dumps(record, ensure_ascii=False) for record in additions) + "\n")
        manifest.update(built_at=datetime.now(timezone.utc).isoformat(),
                        feedback_summary=summary, base_fingerprint=base_fingerprint,
                        require_complete_dialogues=True,
                        required_train_sources=sorted({record["source"] for record in additions}))
        manifest["artifacts_sha256"] = {name: digest(work / name) for name in manifest["artifacts_sha256"]}
        manifest["counts"] = {name: dict(Counter(record["source"] for record in _records(work / f"{name}.jsonl")))
                              for name in ("train", "validation", "test") if (work / f"{name}.jsonl").is_file()}
        manifest["total_rows"] = sum(sum(counts.values()) for counts in manifest["counts"].values())
        (work / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            work.rename(destination)
        except FileExistsError:
            pass  # Another local check prepared the identical content first.
    return destination, fingerprint(destination), summary
