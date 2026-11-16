"""Local, opt-in feedback; only separately reviewed corrections are trainable."""

from datetime import datetime, timezone
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3

from flask import Blueprint, jsonify, request

from location_catalog import get_location
from chat_scope import is_helpful_message


ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE = Path(os.getenv("XANHNON_FEEDBACK_DB", str(ROOT / ".runtime/xanhnon-feedback/feedback.sqlite3")))
REASONS = {"accuracy", "context", "style", "incomplete", "other"}


def record_helpful_message(message, history, location, store, model):
    """A plain 'hữu ích' rates the preceding answer, never its own acknowledgement."""
    if not is_helpful_message(message):
        return None
    from chat_scope import social_intent
    for index in range(len(history) - 2, -1, -2):
        user, assistant = history[index:index + 2]
        if is_helpful_message(user["content"]) or social_intent(user["content"]) in {"thanks", "acknowledge"}:
            continue
        earlier = [history[previous:previous + 2] for previous in range(0, index, 2)
                   if not is_helpful_message(history[previous]["content"])
                   and social_intent(history[previous]["content"]) not in {"thanks", "acknowledge"}]
        context = [turn for pair in earlier[-2:] for turn in pair]
        payload = validate_feedback({"message": user["content"], "reply": assistant["content"],
            "history": context, "location": location["MaDiaDiem"],
            "rating": "helpful", "reason": "other", "comment": "", "correction": ""})
        try:
            store.submit(payload, model)
        except (sqlite3.Error, OSError):
            return {"reply": "Mình chưa lưu được đánh giá. Bạn thử nhắn lại “hữu ích” nhé.", "truncated": False}
        return {"reply": "Cảm ơn bạn, mình đã ghi nhận!", "truncated": False}
    return {"reply": "Cảm ơn bạn nhé!", "truncated": False}


def feedback_events(result):
    yield "data: " + json.dumps({"type": "delta", "text": result["reply"]}, ensure_ascii=False) + "\n\n"
    yield "data: " + json.dumps({"type": "done", **result}, ensure_ascii=False) + "\n\n"


def _text(value, name, maximum, required=True):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(f"{name} không hợp lệ (tối đa {maximum} ký tự).")
    return value.strip()


def dialogue(messages, max_pairs=3):
    if not isinstance(messages, list) or not messages or len(messages) % 2 or len(messages) > max_pairs * 2:
        raise ValueError("Ngữ cảnh góp ý phải gồm các lượt hỏi đáp hoàn chỉnh.")
    result = []
    for index, item in enumerate(messages):
        role = "user" if index % 2 == 0 else "assistant"
        if not isinstance(item, dict) or item.get("role") != role:
            raise ValueError("Vai trò trong ngữ cảnh góp ý không hợp lệ.")
        result.append({"role": role, "content": _text(item.get("content"), "Nội dung hội thoại",
                                                     8000 if role == "user" else 32768)})
    return result


def validate_feedback(body):
    if not isinstance(body, dict):
        raise ValueError("Góp ý phải là một đối tượng JSON.")
    rating = body.get("rating")
    if not isinstance(rating, str) or rating not in {"helpful", "unhelpful"}:
        raise ValueError("Đánh giá không hợp lệ.")
    reason = body.get("reason", "other")
    if not isinstance(reason, str) or reason not in REASONS:
        raise ValueError("Loại góp ý không hợp lệ.")
    comment = _text(body.get("comment", ""), "Góp ý", 1200, required=rating == "unhelpful")
    correction = _text(body.get("correction", ""), "Câu trả lời đề xuất", 2400, required=False)
    history = body.get("history", [])
    if history:
        history = dialogue(history, max_pairs=2)
    elif not isinstance(history, list):
        raise ValueError("Ngữ cảnh góp ý không hợp lệ.")
    return {"message": _text(body.get("message"), "Câu hỏi", 8000),
            "reply": _text(body.get("reply"), "Câu trả lời", 32768),
            "history": history, "location": get_location(body.get("location"))["MaDiaDiem"],
            "rating": rating, "reason": reason, "comment": comment, "correction": correction}


class FeedbackStore:
    def __init__(self, path=DEFAULT_DATABASE):
        self.path = Path(path)

    @contextmanager
    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                connection.execute("""CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL, payload TEXT NOT NULL, model TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending', review TEXT, reviewed_at TEXT
                )""")
                yield connection
        finally:
            connection.close()

    def submit(self, payload, model):
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        fingerprint = hashlib.sha256((model + "\n" + serialized).encode("utf-8")).hexdigest()
        with self._connect() as connection:
            connection.execute("""INSERT OR IGNORE INTO feedback
                (fingerprint, created_at, payload, model) VALUES (?, ?, ?, ?)""",
                (fingerprint, datetime.now(timezone.utc).isoformat(), serialized, model))
            row = connection.execute("SELECT id, status FROM feedback WHERE fingerprint=?", (fingerprint,)).fetchone()
        return dict(row)

    def list(self, status="pending", limit=50):
        if status not in {"pending", "approved", "rejected"}:
            raise ValueError("Unknown review status")
        if not self.path.is_file():
            return []
        with self._connect() as connection:
            if limit is None:
                rows = connection.execute("SELECT * FROM feedback WHERE status=? ORDER BY id", (status,)).fetchall()
            else:
                rows = connection.execute("SELECT * FROM feedback WHERE status=? ORDER BY id LIMIT ?",
                                          (status, min(max(int(limit), 1), 1000))).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"]),
                 "review": json.loads(row["review"]) if row["review"] else None} for row in rows]

    def review(self, identifier, *, approve, reviewer, note, messages=None, source_ids=(),
               kind="dialogue", privacy_reviewed=False, facts_reviewed=False, data_policy="static"):
        reviewer = _text(reviewer, "Người kiểm tra", 120)
        note = _text(note, "Nhận xét kiểm tra", 1200)
        review = {"reviewer": reviewer, "note": note}
        if approve:
            if not privacy_reviewed or not facts_reviewed:
                raise ValueError("Cần kiểm tra nội dung và dữ liệu riêng tư trước khi duyệt.")
            if kind not in {"dialogue", "knowledge"} or data_policy not in {"static", "hypothetical"}:
                raise ValueError("Chỉ duyệt hội thoại/kiến thức ổn định hoặc tình huống giả định.")
            messages = dialogue(messages)
            knowledge = json.loads((ROOT / "data/xanhnon/knowledge.json").read_text(encoding="utf-8"))
            known_sources = knowledge["sources"]
            if (not source_ids or any(not isinstance(source, str) or source not in known_sources for source in source_ids)
                    or (kind == "knowledge" and set(source_ids) <= {"project"})):
                raise ValueError("Bản sửa cần nguồn tham chiếu hợp lệ; kiến thức cần nguồn chuyên môn.")
            # Live readings and forecasts become stale; a reviewer must rewrite them
            # into a self-contained hypothetical example, never label them as current.
            import re
            from chat_knowledge import normalized
            answer = normalized(messages[-1]["content"])
            live = (re.search(r"\d", answer) and
                    re.search(r"\b(hien tai|hom nay|ngay mai|du bao|luc nay|cap nhat)\b", answer))
            if live and (data_policy != "hypothetical" or not any(
                    re.search(r"\b(gia su|gia dinh|gia lap)\b", normalized(turn["content"]))
                    for turn in messages if turn["role"] == "user")):
                raise ValueError("Số liệu theo thời gian phải được viết lại thành ví dụ giả định rõ ràng.")
            review.update(messages=messages, source_ids=sorted(set(source_ids)), kind=kind,
                          data_policy=data_policy, privacy_reviewed=True, facts_reviewed=True)
        with self._connect() as connection:
            updated = connection.execute("UPDATE feedback SET status=?, review=?, reviewed_at=? WHERE id=?",
                ("approved" if approve else "rejected", json.dumps(review, ensure_ascii=False),
                 datetime.now(timezone.utc).isoformat(), identifier))
            if updated.rowcount != 1:
                raise ValueError("Không tìm thấy góp ý.")


def create_feedback_blueprint(store, model_name):
    blueprint = Blueprint("chat_feedback", __name__)

    @blueprint.post("/api/chat/feedback")
    def submit_feedback():
        origin = request.headers.get("Origin")
        if origin not in {None, "null", request.host_url.rstrip("/")}:
            return jsonify({"loi": "Hãy gửi góp ý từ trang Xanh Non đang mở."}), 403
        if request.content_length is not None and request.content_length > 512 * 1024:
            return jsonify({"loi": "Nội dung góp ý quá dài."}), 413
        try:
            payload = validate_feedback(request.get_json(silent=True))
            store.submit(payload, model_name())
        except ValueError as exc:
            return jsonify({"loi": str(exc)}), 400
        except (sqlite3.Error, OSError):
            return jsonify({"loi": "Chưa lưu được góp ý. Bạn thử lại nhé."}), 503
        # The write-only endpoint never exposes review state or other users' text.
        return jsonify({"saved": True, "message": "Đã nhận góp ý của bạn. Cảm ơn bạn nhé!"}), 201

    return blueprint
