"""Learn new question forms from the project's verified sources, never model replies."""

from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3

import chat_knowledge as knowledge
from chat_scope import (assistant_help_intent, expand_shorthand, future_period,
                        is_environment_question, is_followup_question, social_intent)
from prepare_xanhnon_data import make_record


ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE = Path(os.getenv("XANHNON_LEARNING_DB", str(ROOT / ".runtime/xanhnon-learning/questions.sqlite3")))
SOURCE = "environment_chat_learning"
POLICY = "verified-static-questions-v4"


def _normal(text):
    return expand_shorthand(knowledge.normalized(text))


def _sensitive(text):
    plain = _normal(text)
    return bool(re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
        or re.search(r"\b\+?\d[\d .-]{7,}\d\b", text)
        or re.search(r"\b(?:sk-|hf_)[A-Za-z0-9_-]{12,}", text)
        or re.search(r"-?\d{1,3}\.\d+\s*[,;/]\s*-?\d{1,3}\.\d+", text)
        or re.search(r"\b(mat khau|password|api key|access token|secret key|cccd|cmnd|"
                     r"ma sinh vien|so dien thoai|so tai khoan|dia chi nha|ho ten|toi ten|minh ten)\b", plain)
        or re.search(r"\b(?:toi|minh|em)\b.{0,24}\b(bi benh|bi hen|mang thai|chan doan)\b", plain)
        or re.search(r"\bso \d+.{0,30}\b(duong|ngo|hem)\b", plain)
        or re.search(r"\b(ignore previous|system prompt|bo qua.{0,20}(huong dan|chi dan))\b", plain))


@lru_cache(maxsize=2)
def _read_knowledge(path, modified):
    content = Path(path).read_bytes()
    return json.loads(content), hashlib.sha256(content).hexdigest()


@lru_cache(maxsize=4)
def _base_questions(paths):
    trained, heldout = set(), set()
    for filename, modified in paths:
        path = Path(filename)
        if not modified:
            continue
        if path.name == "eval_consultation.json":
            for case in json.loads(path.read_text(encoding="utf-8")):
                heldout.add(_normal(case["question"]))
                heldout.update(_normal(turn["content"]) for turn in case.get("history", []) if turn["role"] == "user")
        else:
            target = trained if path.name == "train.jsonl" else heldout
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    target.update(_normal(turn["content"]) for turn in json.loads(line)["messages"] if turn["role"] == "user")
    return trained, heldout


def _answer(document, variant):
    if variant == "steps":
        return "\n".join(f"{index + 1}. {step}" for index, step in enumerate(document.get("steps", [])))
    if variant == "first_sentence":
        return document["answer"].split(". ", 1)[0].rstrip(".") + "."
    if variant == "particle_size":
        return document["answer"].split("; ", 1)[0].rstrip(".") + "." if document["id"] == "pm25_definition" else ""
    return document.get(variant, "") if variant in {"answer", "answer_without_filter"} else ""


class ConversationLearner:
    def __init__(self, database=DEFAULT_DATABASE, base_dir=None):
        self.path = Path(database)
        self.base_dir = Path(base_dir) if base_dir is not None else ROOT / "data/xanhnon"
        self.enabled = os.getenv("XANHNON_AUTO_LEARN", "1") != "0"

    @contextmanager
    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=3)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                connection.execute("""CREATE TABLE IF NOT EXISTS questions (
                    question_key TEXT PRIMARY KEY, question TEXT NOT NULL, context_user TEXT NOT NULL,
                    status TEXT NOT NULL, document_id TEXT, variant TEXT,
                    knowledge_hash TEXT NOT NULL, policy TEXT NOT NULL,
                    created_at TEXT NOT NULL, last_seen TEXT NOT NULL, seen_count INTEGER NOT NULL
                )""")
                yield connection
        finally:
            connection.close()

    def _knowledge(self):
        path = knowledge.KNOWLEDGE_PATH
        pack, version = _read_knowledge(str(path), path.stat().st_mtime_ns)
        if (not isinstance(pack, dict) or not isinstance(pack.get("sources"), dict)
                or not isinstance(pack.get("documents"), list)):
            raise ValueError("Invalid verified knowledge pack")
        for doc in pack["documents"]:
            if (not isinstance(doc, dict) or not isinstance(doc.get("id"), str)
                    or not isinstance(doc.get("answer"), str) or not isinstance(doc.get("title"), str)
                    or not isinstance(doc.get("questions"), list)
                    or not all(isinstance(question, str) for question in doc["questions"])
                    or not isinstance(doc.get("source_ids"), list)):
                raise ValueError("Invalid verified knowledge document")
        return pack, version

    def _sets(self):
        paths = [self.base_dir / name for name in ("train.jsonl", "validation.jsonl", "test.jsonl", "eval_consultation.json")]
        return _base_questions(tuple((str(path), path.stat().st_mtime_ns if path.is_file() else 0) for path in paths))

    def _context(self, message, history):
        if not is_followup_question(message):
            return ""
        for index in range(len(history) - 1, -1, -1):
            turn = history[index]
            if turn.get("role") != "user" or social_intent(turn["content"]):
                continue
            if is_followup_question(turn["content"]):
                continue
            return turn["content"] if is_environment_question(turn["content"], history[:index]) else ""
        return ""

    def _candidate(self, question, context, pack):
        combined = _normal(context + " " + question)
        # Numerical/current/forecast answers must continue to read runtime data.
        without_terms = re.sub(r"\b(pm25|pm10|pm1|co2|no2|so2|o3)\b", "", combined)
        if (re.search(r"\d", without_terms) or future_period(combined)
                or re.search(r"\b(hom nay|hien tai|bay gio|luc nay|hom qua|so do|so lieu|du lieu giam sat)\b", combined)):
            return "needs_data", None, None
        if re.search(r"\b(thuoc|chan doan|chua benh|cap cuu)\b", combined):
            return "needs_source", None, None
        history = [{"role": "user", "content": _normal(context)}] if context else []
        detail = bool(re.search(r"\b(chi tiet|day du|tung buoc|liet ke|phan tich sau|giai thich ky)\b", combined))
        answer = knowledge.practical_answer(_normal(question), history, detailed=detail, documents=pack["documents"])
        if answer is None and not detail:
            answer = knowledge.concept_answer(_normal(question), history, documents=pack["documents"])
        if answer is None:
            return "needs_source", None, None
        for document in pack["documents"]:
            sources = document.get("source_ids", [])
            if not sources or not all(source in pack["sources"] for source in sources):
                continue
            if not any(pack["sources"][source].get("type") == "official" for source in sources):
                continue
            for variant in ("answer", "answer_without_filter", "steps", "first_sentence", "particle_size"):
                if answer == _answer(document, variant):
                    if len(question) + len(context) + len(answer) > 1600:
                        return "needs_review", None, None
                    return "learned", document["id"], variant
        return "needs_source", None, None

    def _checked_answer(self, row, pack, version):
        if row["status"] != "learned" or row["knowledge_hash"] != version or row["policy"] != POLICY:
            return None
        doc = next((doc for doc in pack["documents"] if doc["id"] == row["document_id"]), None)
        return _answer(doc, row["variant"]) if doc else None

    def observe(self, message, history=()):
        """Capture only new suitable user questions; return a verified static answer when available."""
        if (not self.enabled or not message.strip() or len(message) > 1600 or _sensitive(message)
                or social_intent(message) or assistant_help_intent(message)
                or not is_environment_question(message, history)):
            return None
        context = self._context(message, history)
        if len(context) > 1600 or _sensitive(context):
            return None
        trained, heldout = self._sets()
        if _normal(message) in heldout or (context and _normal(context) in heldout):
            return None
        pack, version = self._knowledge()
        known = {_normal(question) for doc in pack["documents"] for question in doc["questions"] + [doc["title"]]}
        if not context and _normal(message) in trained | known:
            return None
        key = hashlib.sha256((_normal(context) + "\n" + _normal(message)).encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            old = connection.execute("SELECT * FROM questions WHERE question_key=?", (key,)).fetchone()
            if old and old["knowledge_hash"] == version and old["policy"] == POLICY:
                connection.execute("UPDATE questions SET seen_count=seen_count+1, last_seen=? WHERE question_key=?", (now, key))
                return self._checked_answer(old, pack, version)
            status, document_id, variant = self._candidate(message, context, pack)
            connection.execute("""INSERT INTO questions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(question_key) DO UPDATE SET status=excluded.status, document_id=excluded.document_id,
                variant=excluded.variant, knowledge_hash=excluded.knowledge_hash, policy=excluded.policy,
                last_seen=excluded.last_seen, seen_count=questions.seen_count+1""",
                (key, message.strip(), context, status, document_id, variant, version, POLICY, now, now))
            row = connection.execute("SELECT * FROM questions WHERE question_key=?", (key,)).fetchone()
            return self._checked_answer(row, pack, version)

    def questions(self, status=None, limit=50):
        if not self.path.is_file():
            return []
        with self._connect() as connection:
            condition, args = ("WHERE status=?", [status]) if status else ("", [])
            rows = connection.execute(f"SELECT * FROM questions {condition} ORDER BY created_at LIMIT ?",
                                      (*args, min(max(int(limit), 1), 1000))).fetchall()
        return [dict(row) for row in rows]

    def stats(self):
        if not self.path.is_file():
            return {}
        with self._connect() as connection:
            return {row[0]: row[1] for row in connection.execute("SELECT status, COUNT(*) FROM questions GROUP BY status")}

    def recheck(self, limit=32):
        if not self.enabled or not self.path.is_file():
            return 0
        pack, version = self._knowledge()
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM questions WHERE knowledge_hash!=? OR policy!=? LIMIT ?",
                                      (version, POLICY, limit)).fetchall()
        for row in rows:
            status, document_id, variant = self._candidate(row["question"], row["context_user"], pack)
            with self._connect() as connection:
                connection.execute("UPDATE questions SET status=?, document_id=?, variant=?, knowledge_hash=?, policy=? WHERE question_key=?",
                                   (status, document_id, variant, version, POLICY, row["question_key"]))
        return len(rows)

    def training_records(self):
        if not self.enabled or not self.path.is_file():
            return []
        pack, version = self._knowledge()
        _, heldout = self._sets()
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM questions WHERE status='learned' ORDER BY question_key").fetchall()
        result = []
        for row in rows:
            if _normal(row["question"]) in heldout or _normal(row["context_user"]) in heldout:
                continue
            answer = self._checked_answer(row, pack, version)
            if not answer:
                continue
            doc = next(doc for doc in pack["documents"] if doc["id"] == row["document_id"])
            question = row["question"]
            if row["context_user"]:
                question = f"Chủ đề đang trao đổi: {row['context_user']}\nCâu hỏi tiếp theo: {question}"
            result.append(make_record([{"role": "user", "content": question}, {"role": "assistant", "content": answer}],
                SOURCE, row["question_key"], source_ids=doc["source_ids"], document_id=doc["id"],
                knowledge_sha256=version, review="automatic_existing_verified_source", original_question=row["question"],
                context_user=row["context_user"],
                supervise_last_assistant_only=True))
        return result
