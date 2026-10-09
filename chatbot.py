"""Local Xanh Non inference; weights and tokenizer stay on this machine."""

import json
import logging
import os
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, Thread

from native_chatbot import NativeChatbot
from location_catalog import get_location


ROOT = Path(__file__).resolve().parent
MODEL_DIR = Path(os.getenv("CHATBOT_MODEL_DIR", str(ROOT / "models" / "xanhnon-qwen2.5-0.5b-vietnamese")))
NATIVE_BINARY = Path(os.getenv("CHATBOT_LLAMA_SERVER", str(ROOT / ".runtime" / "llama-bin" / ("llama-server.exe" if os.name == "nt" else "llama-server"))))
GGUF_PATH = Path(os.getenv("CHATBOT_GGUF_PATH", str(ROOT / "models" / "xanhnon-f16.gguf")))
MAX_NEW_TOKENS = int(os.getenv("CHATBOT_MAX_NEW_TOKENS", "-1"))
if MAX_NEW_TOKENS != -1:
    MAX_NEW_TOKENS = min(max(MAX_NEW_TOKENS, 32), 4096)
MAX_INPUT_TOKENS = 8192
_runtime = None
_runtime_state = "cold"
_runtime_lock = Lock()
_generation_lock = Lock()
logger = logging.getLogger(__name__)


class ChatbotBusy(Exception):
    pass


def validate_chat(body):
    """Accept a current question and up to four complete conversation turns."""
    if not isinstance(body, dict):
        raise ValueError("Yêu cầu phải là JSON gồm message và history.")
    message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Hãy nhập câu hỏi cho Xanh Non.")
    if len(message) > 8000:
        raise ValueError("Câu hỏi tối đa 8000 ký tự.")
    history = body.get("history", [])
    if not isinstance(history, list) or len(history) > 8 or len(history) % 2:
        raise ValueError("Lịch sử tối đa 4 lượt hỏi và trả lời hoàn chỉnh.")
    cleaned = []
    for index, item in enumerate(history):
        expected_role = "user" if index % 2 == 0 else "assistant"
        if (not isinstance(item, dict) or item.get("role") != expected_role
                or not isinstance(item.get("content"), str)
                or not item["content"].strip() or len(item["content"]) > 32768):
            raise ValueError("Lịch sử hội thoại không hợp lệ.")
        cleaned.append({"role": expected_role, "content": item["content"].strip()})
    return message.strip(), cleaned


def _load_runtime():
    global _runtime, _runtime_state
    if _runtime is not None:
        return _runtime
    with _runtime_lock:
        if _runtime is not None:
            return _runtime
        _runtime_state = "loading"
        try:
            _runtime = _create_runtime()
            _runtime_state = "ready"
            return _runtime
        except Exception:
            _runtime_state = "error"
            raise


def runtime_status():
    return {"state": _runtime_state}


def warm_up_chatbot():
    def load():
        try:
            _load_runtime()
        except Exception:
            logger.exception("Không nạp trước được Xanh Non")
    Thread(target=load, name="xanhnon-warmup", daemon=True).start()


def _create_runtime():
    backend = os.getenv("CHATBOT_BACKEND", "auto")
    if backend not in {"auto", "llama_cpp", "transformers"}:
        raise ValueError("CHATBOT_BACKEND must be auto, llama_cpp or transformers")
    if backend == "llama_cpp" or (backend == "auto" and NATIVE_BINARY.is_file() and GGUF_PATH.is_file()):
        return NativeChatbot(
            NATIVE_BINARY, GGUF_PATH,
            min(max(int(os.getenv("CHATBOT_CPU_THREADS", "4")), 1), 8),
            MAX_INPUT_TOKENS, MAX_NEW_TOKENS,
        )
    if not (MODEL_DIR / "model.safetensors").is_file():
        raise FileNotFoundError("Không tìm thấy model.safetensors trong CHATBOT_MODEL_DIR.")

    # Lazy imports keep dashboard startup independent of the language model.
    os.environ.setdefault("USE_TF", "0")
    os.environ.setdefault("USE_FLAX", "0")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        torch.set_num_threads(min(max(int(os.getenv("CHATBOT_CPU_THREADS", "4")), 1), 8))
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_DIR, local_files_only=True, trust_remote_code=False, use_fast=False,
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIR, local_files_only=True, trust_remote_code=False,
        use_safetensors=True, dtype=torch.float16 if device == "cuda" else torch.float32,
        attn_implementation="sdpa",
    ).eval()
    model.to(device)
    return torch, tokenizer, model, device


def _system_prompt(snapshot):
    location = snapshot.get("DiaDiem") if snapshot else None
    location = location or get_location()
    return (
        f"Bạn là Xanh Non, trợ lý môi trường. Địa điểm đang chọn: {location['Ten']}. "
        "Trả lời bằng tiếng Việt, rõ ràng và đủ ý theo yêu cầu của người dùng. "
        "Địa điểm đang chọn là khu vực giám sát được ứng dụng cung cấp. "
        "Dùng dữ liệu bảng giám sát kèm câu hỏi để trả lời; chỉ số thiếu thì nói chưa có. "
        "Tên địa điểm vẫn được xác định khi thiếu số đo."
    )


def _dashboard_context(snapshot):
    location = (snapshot or {}).get("DiaDiem") or get_location()
    prompt = f"Địa điểm đang chọn trên bảng giám sát: {location['Ten']}.\n"
    if not snapshot or not snapshot.get("DuLieu"):
        return prompt + "Chưa có số liệu môi trường hiện tại."
    readings = snapshot.get("DuLieu", {})
    fields = (
        ("US_AQI", "US AQI", ""), ("PM25", "PM2.5", "µg/m³"),
        ("PM10", "PM10", "µg/m³"), ("NhietDo", "Nhiệt độ", "°C"),
        ("DoAm", "Độ ẩm", "%"), ("TiengOn", "Tiếng ồn", "dBA"),
    )
    values = [f"{label}: {readings[field]} {unit}" if readings.get(field) is not None
              else f"{label}: chưa có dữ liệu" for field, label, unit in fields]
    timestamp = str(snapshot.get("ThoiGian", "chưa rõ"))[:16].replace("T", " ")
    prompt += f"Cập nhật {timestamp}: " + "; ".join(values) + ".\n"
    prompt += f"Open-Meteo theo tọa độ tham chiếu {location['Ten']}.\n"
    if readings.get("TiengOn") is not None:
        prompt += f"Tiếng ồn: tổng hợp quanh {location['TenKhuVucTiengOn']} (NoiseCapture), không phải đo trực tiếp.\n"
    analysis = snapshot.get("PhanTich", {})
    if analysis:
        prompt += f"Đánh giá AQI: {analysis.get('KetQua', 'chưa có')}."
    return prompt


def _generate(message, history, snapshot, on_text=None, cancelled=None):
    runtime = _load_runtime()
    messages = [{"role": "system", "content": _system_prompt(snapshot)}] + history + [
        {"role": "user", "content": f"Dữ liệu bảng giám sát do ứng dụng cung cấp:\n{_dashboard_context(snapshot)}\n\nCâu hỏi của người dùng:\n{message}"}
    ]
    if isinstance(runtime, NativeChatbot):
        return runtime.generate(messages, MAX_NEW_TOKENS, on_text, cancelled)
    torch, tokenizer, model, device = runtime
    while True:
        inputs = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True,
            return_tensors="pt", return_dict=True,
        )
        if inputs["input_ids"].shape[1] <= MAX_INPUT_TOKENS:
            break
        if len(messages) <= 2:
            raise ValueError("Câu hỏi quá dài với ngữ cảnh hiện tại. Hãy rút ngắn câu hỏi.")
        del messages[1:3]
    inputs = inputs.to(device)
    options = {}
    streamer = None
    if on_text is not None:
        from transformers import TextStreamer

        class LiveText(TextStreamer):
            def on_finalized_text(self, text, stream_end=False):
                if text:
                    on_text(text)

        streamer = LiveText(tokenizer, skip_prompt=True, skip_special_tokens=True)
    if cancelled is not None:
        from transformers import StoppingCriteria, StoppingCriteriaList

        class Disconnected(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs):
                return cancelled.is_set()

        options["stopping_criteria"] = StoppingCriteriaList([Disconnected()])
    end_tokens = model.generation_config.eos_token_id
    end_tokens = end_tokens if isinstance(end_tokens, list) else [end_tokens]
    prompt_ids = inputs["input_ids"]
    token_parts = []
    block_size = MAX_NEW_TOKENS if MAX_NEW_TOKENS > 0 else 2048
    context_size = model.config.max_position_embeddings
    with torch.inference_mode():
        while True:
            output = model.generate(
                **inputs, max_new_tokens=block_size,
                do_sample=False, temperature=None, top_p=None, top_k=None,
                repetition_penalty=1.1, use_cache=True, streamer=streamer,
                pad_token_id=tokenizer.pad_token_id, **options,
            )
            new_tokens = output[0, inputs["input_ids"].shape[1]:].detach().cpu()
            if not new_tokens.numel():
                raise RuntimeError("The model returned an empty reply")
            token_parts.append(new_tokens)
            if (int(new_tokens[-1]) in end_tokens or MAX_NEW_TOKENS > 0
                    or (cancelled is not None and cancelled.is_set())):
                break
            # Continue the same assistant reply. Retain the prompt and the newest
            # generated tokens when the model's context window becomes full.
            tail_budget = context_size - prompt_ids.shape[1] - block_size
            tail = torch.cat(token_parts)[-tail_budget:].to(device).unsqueeze(0)
            input_ids = torch.cat((prompt_ids, tail), dim=1)
            inputs = {"input_ids": input_ids, "attention_mask": torch.ones_like(input_ids)}
    tokens = torch.cat(token_parts)
    reply = tokenizer.decode(tokens, skip_special_tokens=True).strip()
    if not reply:
        raise RuntimeError("The model returned an empty reply")
    return {"reply": reply, "truncated": int(tokens[-1]) not in end_tokens}


def _acquire_generation():
    if not _generation_lock.acquire(blocking=False):
        raise ChatbotBusy("Xanh Non đang trả lời một câu hỏi khác. Hãy thử lại sau ít giây.")


def generate_reply(message, history, snapshot=None):
    _acquire_generation()
    try:
        return _generate(message, history, snapshot)
    finally:
        _generation_lock.release()


def stream_reply(message, history, snapshot=None):
    """Acquire before returning HTTP headers; release after generation/disconnect."""
    _acquire_generation()
    queue = Queue()
    cancelled = Event()

    def generate():
        try:
            queue.put({"type": "status", "text": "Xanh Non đang chuẩn bị…"})
            result = _generate(
                message, history, snapshot,
                lambda text: queue.put({"type": "delta", "text": text}), cancelled,
            )
            queue.put({"type": "done", **result})
        except Exception:
            logger.exception("Không tạo được phản hồi trực tiếp từ Xanh Non")
            queue.put({"type": "error", "loi": "Xanh Non chưa tạo được câu trả lời. Hãy thử lại."})
        finally:
            _generation_lock.release()

    try:
        Thread(target=generate, name="xanhnon-reply", daemon=True).start()
    except Exception:
        _generation_lock.release()
        raise

    def events():
        try:
            while True:
                try:
                    event = queue.get(timeout=4)
                except Empty:
                    yield ": keepalive\n\n"
                    continue
                yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                if event["type"] in {"done", "error"}:
                    break
        finally:
            cancelled.set()

    return events()
