"""Local Xanh Non inference; weights and tokenizer stay on this machine."""

import json
import logging
import math
import os
from pathlib import Path
from queue import Empty, Queue
import re
from threading import Event, Lock, Thread
import unicodedata
from datetime import timedelta

from native_chatbot import NativeChatbot
from chat_output import ReplyFilter, clean_reply, has_dangling_intro
from chat_knowledge import concept_answer, exact_answer, reference_context, advice_topic, practical_answer
from chat_scope import (assistant_help_intent, is_activity_question,
                        is_activity_suggestion, is_environment_question, is_followup_question,
                        future_period, social_intent, expand_shorthand, current_time_reply,
                        brief_reply_request, uncertain_reply, is_time_followup, strip_time_references)
from chat_air_data import AirDataUnavailable, forecast_aqi, forecast_window, get_air_data
from chat_weather_data import WeatherDataUnavailable, forecast_weather, get_weather_data
from chat_clarification import (clarification_reply, resolve_topic_choice,
                                single_topic_question, topic_kinds)
from location_catalog import (LOCATIONS, get_location, named_location,
                              location_followup, without_locations,location_mentions)
from chat_time_context import explicit_clock,without_clock,clock_label,invalid_clock
from chat_air_data import local_now
from model_release import read_release
from training_state import training_in_progress


ROOT = Path(__file__).resolve().parent
ACTIVE_RELEASE = read_release(ROOT)
MODEL_DIR = Path(os.getenv("CHATBOT_MODEL_DIR", str(ACTIVE_RELEASE.get("base_model", ROOT / "models" / "xanhnon-qwen2.5-0.5b-vietnamese"))))
NATIVE_BINARY = Path(os.getenv("CHATBOT_LLAMA_SERVER", str(ROOT / ".runtime" / "llama-bin" / ("llama-server.exe" if os.name == "nt" else "llama-server"))))
GGUF_PATH = Path(os.getenv("CHATBOT_GGUF_PATH", str(ACTIVE_RELEASE.get("gguf", ROOT / "models" / "xanhnon-f16.gguf"))))
ADAPTER_DIR = ACTIVE_RELEASE.get("adapter") if ACTIVE_RELEASE.get("base_model") == MODEL_DIR.resolve() else None
if "CHATBOT_ADAPTER_PATH" in os.environ:
    ADAPTER_DIR = Path(os.environ["CHATBOT_ADAPTER_PATH"]) if os.environ["CHATBOT_ADAPTER_PATH"] else None
MAX_NEW_TOKENS = int(os.getenv("CHATBOT_MAX_NEW_TOKENS", "256"))
if MAX_NEW_TOKENS != -1:
    MAX_NEW_TOKENS = min(max(MAX_NEW_TOKENS, 32), 4096)
DETAIL_MAX_NEW_TOKENS = min(max(int(os.getenv("CHATBOT_DETAIL_MAX_NEW_TOKENS", "768")), 32), 4096)
MAX_INPUT_TOKENS = min(max(int(os.getenv("CHATBOT_MAX_INPUT_TOKENS", "8192")), 512), 8192)
MODEL_PROMPT_PROFILE = os.getenv("CHATBOT_PROMPT_PROFILE", "legacy")
if MODEL_PROMPT_PROFILE not in {"legacy", "grounded-v15", "grounded-v16"}:
    raise ValueError("CHATBOT_PROMPT_PROFILE must be legacy, grounded-v15 or grounded-v16")
MAX_HISTORY_TURNS = 8
_runtime = None
_runtime_state = "cold"
_runtime_lock = Lock()
_generation_lock = Lock()
logger = logging.getLogger(__name__)


class ChatbotBusy(Exception):
    pass


def _training_chat_allowed():
    """Keep the stable native model usable when RAM permits background training."""
    if os.getenv("CHATBOT_CHAT_DURING_TRAINING", "1") != "1":
        return False
    if os.getenv("CHATBOT_BACKEND", "auto") not in {"auto", "llama_cpp"}:
        return False
    if not NATIVE_BINARY.is_file() or not GGUF_PATH.is_file():
        return False
    if _runtime is not None and not isinstance(_runtime, NativeChatbot):
        return False
    import psutil
    required = 2 if _runtime is not None else 3
    return psutil.virtual_memory().available >= required * 2**30


def validate_chat(body):
    """Accept the current question and a bounded number of complete turns."""
    if not isinstance(body, dict):
        raise ValueError("Yêu cầu phải là JSON gồm message và history.")
    message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Hãy nhập câu hỏi cho Xanh Non.")
    if len(message) > 8000:
        raise ValueError("Câu hỏi tối đa 8000 ký tự.")
    history = body.get("history", [])
    if not isinstance(history, list) or len(history) > MAX_HISTORY_TURNS * 2 or len(history) % 2:
        raise ValueError(f"Lịch sử tối đa {MAX_HISTORY_TURNS} lượt hỏi và trả lời hoàn chỉnh.")
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
    if training_in_progress() and not _training_chat_allowed():
        raise ChatbotBusy("Xanh Non đang cập nhật mô hình. Bạn hỏi lại câu này sau giúp mình nhé.")
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
    if training_in_progress():
        return {"state": _runtime_state, "background_training": True} if _training_chat_allowed() else {"state": "training"}
    return {"state": _runtime_state}


def warm_up_chatbot():
    if training_in_progress() and not _training_chat_allowed():
        return
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
        threads = min(max(int(os.getenv("CHATBOT_CPU_THREADS", "4")), 1), 8)
        if training_in_progress():
            threads = min(threads, 2)
        return NativeChatbot(
            NATIVE_BINARY, GGUF_PATH,
            threads,
            MAX_INPUT_TOKENS, -1 if MAX_NEW_TOKENS == -1 else max(MAX_NEW_TOKENS, DETAIL_MAX_NEW_TOKENS),
            gpu_layers=int(os.getenv("CHATBOT_GPU_LAYERS", "0")),
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
    if ADAPTER_DIR is not None:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, ADAPTER_DIR, local_files_only=True, is_trainable=False).eval()
    model.to(device)
    return torch, tokenizer, model, device


def _plain_question(message):
    text = unicodedata.normalize("NFD", message.lower().replace("đ", "d"))
    return expand_shorthand(" ".join("".join(char for char in text if not unicodedata.combining(char)).split()))


def _wants_detail(message, history):
    question = _plain_question(message)
    if re.search(r"\b(ngan gon|ngan thoi|ngan hon|gon hon|rut gon|tom tat|tra loi ngan|khong (can )?((tra loi|giai thich|phan tich) )?(qua )?(chi tiet|dai dong))\b", question):
        return False
    if re.search(r"\b(viet tiep|tiep tuc cau tra loi)\b", question):
        previous = next((item["content"] for item in reversed(history) if item["role"] == "user"), "")
        return _wants_detail(previous, history[:-2]) if previous else False
    return bool(re.search(r"\b(chi tiet|day du|tung buoc|phan tich sau|giai thich ky|liet ke|so sanh)\b", question))


def _system_prompt(snapshot, detailed=False, selected_fields=None):
    location = snapshot.get("DiaDiem") if snapshot else None
    location = location or get_location()
    style = ("Giải thích rõ trong khoảng 4–6 câu, tập trung vào câu hỏi. "
             if detailed else
             "Trả lời trực tiếp trong 1–3 câu ngắn, tối đa khoảng 60 từ. ")
    prompt = (
        f"Bạn là Xanh Non, trợ lý môi trường. Địa điểm đang chọn: {location['Ten']}. "
        "Xưng mình và gọi người dùng là bạn, trò chuyện bằng tiếng Việt tự nhiên. " + style +
        "Chỉ nói thông tin cần để trả lời, dùng đoạn văn ngắn. "
        "Giải thích kiến thức theo tài liệu tham chiếu; dùng số đo được cung cấp khi hỏi về hiện tại. "
        "Giữ đúng địa điểm, đơn vị và giá trị. Chỉ báo thiếu số liệu nếu cần số đó để trả lời. "
        "Câu hỏi giả định dùng giá trị trong giả định. "
        "Số đo hiện tại không phải dữ liệu dự báo; không dùng để kết luận về tương lai. "
        "Khi tư vấn, nêu kết luận, căn cứ liên quan và hành động phù hợp với mức ô nhiễm. "
        "Nếu thiếu thông tin làm thay đổi lời khuyên, hỏi lại một câu cụ thể. "
        "Nếu chưa rõ người dùng đang hỏi chủ đề nào, hỏi làm rõ bằng một câu ngắn; "
        "khi ngữ cảnh đã rõ thì trả lời tiếp, không bắt người dùng nhắc lại. "
        "Phân biệt số liệu mô hình theo khu vực với phép đo tại vị trí người dùng. "
        "Không phủ nhận khả năng đọc dữ liệu đã được ứng dụng cung cấp. "
        "Không khẳng định nguồn gây ô nhiễm cụ thể chỉ từ một chỉ số; phân biệt nguyên nhân có thể và nguyên nhân đã kiểm chứng. "
        "Khi hỏi cách xử lý, đưa ngay các biện pháp cụ thể và lý do ngắn; không kết thúc chỉ bằng câu dẫn hứa liệt kê. "
    )
    if selected_fields is None or "US_AQI" in selected_fields:
        prompt += "Lời khuyên về hoạt động ngoài trời dựa vào hướng dẫn AQI được cung cấp. "
    if selected_fields is None or set(selected_fields) & {"US_AQI", "PM25", "PM10", "TiengOn"}:
        prompt += "Thông tin sức khỏe chỉ giải thích các tác động đã có trong kiến thức tham chiếu."
    return prompt


def _reading(value, nonnegative=True):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return value if not nonnegative or value >= 0 else None


def _aqi_guidance(aqi):
    """AirNow US AQI categories; activity guidance in air-quality-guide-for-particle-pollution_0.pdf."""
    if aqi <= 50:
        return "Tốt", "Có thể hoạt động ngoài trời bình thường xét riêng về chất lượng không khí."
    if aqi <= 100:
        return "Trung bình", "Có thể ra ngoài; người nhạy cảm nên giảm thời gian và cường độ hoạt động."
    if aqi <= 150:
        return "Kém", "Nhóm nhạy cảm nên giảm thời gian và cường độ hoạt động ngoài trời."
    if aqi <= 200:
        return "Xấu", "Nên giảm hoạt động ngoài trời kéo dài hoặc gắng sức; nhóm nhạy cảm nên chuyển các hoạt động đó vào trong nhà."
    if aqi <= 300:
        return "Rất xấu", "Tránh hoạt động ngoài trời kéo dài hoặc gắng sức; nhóm nhạy cảm nên tránh hoạt động thể chất ngoài trời."
    return "Nguy hại", "Tránh hoạt động thể chất ngoài trời; nhóm nhạy cảm nên ở trong nhà."


def _provided_aqi_reply(message):
    """Classify an explicitly supplied US AQI without borrowing live readings."""
    question = _plain_question(message)
    if re.search(r"\b(vn aqi|eu aqi|european aqi|aqi viet nam|aqi chau au|aqi trung quoc)\b", question):
        return None
    value = re.search(r"\b(?:us\s+)?aqi\s*(?:(?:la|len|bang|o muc|=|:)\s*)?(-?\d+(?:[.,]\d+)?)\b", question)
    if not value or not re.search(r"\b(muc nao|thuoc muc|thuoc loai|mau gi|mau nao|tot hay xau|xau hay tot|goi la gi)\b", question):
        return None
    # A question comparing particles and indices needs its own units explanation.
    if re.search(r"\b(pm2[.,]?5|pm10|nong do|dong nghia|quy doi)\b", question):
        return None
    number = float(value[1].replace(',', '.'))
    if not 0 <= number <= 500:
        return f"Bạn kiểm tra lại giá trị {number:g} nhé; bảng phân mức US AQI đang dùng có khoảng 0–500."
    label, advice = _aqi_guidance(number)
    color = next(color for maximum, color in [(50,'xanh lá'), (100,'vàng'), (150,'cam'),
                                               (200,'đỏ'), (300,'tím'), (500,'nâu đỏ')] if number <= maximum)
    answer = f"Với US AQI {number:g}, mức tương ứng là {label} ({color})."
    if is_activity_question(message) or re.search(r"\b(nen lam gi|tu van|khuyen|chu y)\b", question):
        answer += " " + advice
    return answer


def _requested_fields(message, history=()):
    """Choose readings for the current topic, including explicit combinations."""
    question = _plain_question(message)
    # Definitions and hypothetical situations do not describe current readings.
    hypothetical = re.search(r"\b(gia su|gia dinh|neu)\b", question)
    conceptual = re.search(
        r"\b(la gi|nghia la gi|khac nhau|phan biet|tu dau|nguon goc|phat sinh|"
        r"nho toi muc nao|di sau|vao phoi|het lo|tranh het|trong nha thi|"
        r"cach tinh|tai sao|vi sao)\b", question)
    explanation = re.search(r"\b(giai thich|de hieu|hieu hon)\b", question)
    current = re.search(r"\b(hien tai|bay gio|hom nay|luc nay|dang|bao nhieu)\b", question)
    activity = is_activity_question(message, history)
    if future_period(message) or hypothetical or (conceptual and not current) or (explanation and not current and not activity):
        return ()
    selected = set()
    if re.search(r"\b(thoi tiet|weather)\b", question):
        selected.update(("NhietDo", "DoAm"))
    if re.search(r"\b(nhiet do|bao nhieu do|temperature)\b", question):
        selected.add("NhietDo")
    if re.search(r"\b(do am|humidity)\b", question):
        selected.add("DoAm")
    if re.search(r"\b(tieng on|do on|dba|decibel|deciben|noise)\b", question):
        selected.add("TiengOn")
    if re.search(r"\b(aqi|chat luong khong khi|khong khi|o nhiem khong khi|air quality)\b", question):
        selected.add("US_AQI")
    if re.search(r"\bpm\s*2[.,]?\s*5\b|\bbui min\b", question):
        selected.add("PM25")
    if re.search(r"\bpm\s*10\b", question):
        selected.add("PM10")
    if activity:
        selected.add("US_AQI")
    if selected:
        return tuple(sorted(selected))
    if re.search(r"\b(du lieu|so lieu|tong quan|cac chi so|moi chi so|toan bo chi so)\b", question):
        return None  # A request for the whole dashboard can use every field.
    if history and is_followup_question(message):
        for index in range(len(history) - 1, -1, -1):
            if history[index]["role"] == "user" and not social_intent(history[index]["content"]):
                return _requested_fields(history[index]["content"], history[:index])
    return ()


def _dashboard_context(snapshot, selected_fields=None):
    location = (snapshot or {}).get("DiaDiem") or get_location()
    prompt = f"Địa điểm đang chọn trên bảng giám sát: {location['Ten']}.\n"
    if selected_fields is not None and not selected_fields:
        return prompt
    if (not snapshot or not snapshot.get("DuLieu")) and selected_fields is None:
        return prompt + "Chưa có số liệu môi trường hiện tại."
    readings = (snapshot or {}).get("DuLieu") or {}
    fields = (
        ("US_AQI", "US AQI", ""), ("PM25", "PM2.5", "µg/m³"),
        ("PM10", "PM10", "µg/m³"), ("NhietDo", "Nhiệt độ", "°C"),
        ("DoAm", "Độ ẩm", "%"), ("TiengOn", "Tiếng ồn", "dBA"),
    )
    if selected_fields is not None:
        fields = tuple(item for item in fields if item[0] in selected_fields)
    values = []
    for field, label, unit in fields:
        value = _reading(readings.get(field), nonnegative=field != "NhietDo")
        values.append(f"{label}: {value:g} {unit}".rstrip() if value is not None
                      else f"{label}: chưa có dữ liệu")
    timestamp = str((snapshot or {}).get("ThoiGian", "chưa rõ"))[:16].replace("T", " ")
    prompt += f"Cập nhật {timestamp}: " + "; ".join(values) + ".\n"
    if (snapshot or {}).get("DuLieuCu"):
        prompt += "Đây là số liệu đã cũ; không mô tả như điều kiện hiện tại.\n"
    if (snapshot or {}).get("ThoiTietCu") and any(field in {"NhietDo", "DoAm"} for field, _, _ in fields):
        prompt += f"Nhiệt độ/độ ẩm là số liệu cũ từ {snapshot.get('ThoiGianThoiTiet', 'chưa rõ')}, không phải thời điểm vừa lấy AQI.\n"
    if any(field != "TiengOn" for field, _, _ in fields):
        prompt += f"Open-Meteo theo tọa độ tham chiếu {location['Ten']}.\n"
    if (selected_fields is None or "TiengOn" in selected_fields) and _reading(readings.get("TiengOn")) is not None:
        prompt += f"Tiếng ồn: tổng hợp quanh {location['TenKhuVucTiengOn']} (NoiseCapture), không phải đo trực tiếp.\n"
    if selected_fields is not None and "US_AQI" not in selected_fields:
        return prompt
    aqi = _reading(readings.get("US_AQI"))
    if aqi is not None:
        category, advice = _aqi_guidance(aqi)
        prompt += f"Mức US AQI: {category}. Hướng dẫn hoạt động theo AQI (AirNow/EPA): {advice}"
    else:
        prompt += "Chưa có US AQI hợp lệ; không xác định mức AQI từ PM2.5 hay nhãn phân tích cũ."
    return prompt


def _mentions_other_location(message, location):
    _,mentions=location_mentions(message)
    return any(place['MaDiaDiem']!=location.get('MaDiaDiem') for _,_,place in mentions)


def _weather_reply(message, history, snapshot):
    """Current weather facts need neither an LLM nor unrelated missing-data notes."""
    if _wants_detail(message, history) or future_period(message):
        return None
    fields = _requested_fields(message, history)
    if not fields or not set(fields) <= {"NhietDo", "DoAm"}:
        return None
    # Đà Nẵng is a place name, not the weather condition "nắng".
    question = _plain_question(without_locations(message))
    if not re.search(r"\b(thoi tiet|nhiet do|bao nhieu do|do am|weather|temperature|humidity)\b", question):
        return None
    if re.search(
            r"\b(la gi|nghia la gi|tai sao|vi sao|cach|anh huong|tac dong|nguyen nhan|"
            r"so sanh|trung binh|lich su|du bao|ngay mai|ngay kia|tuan toi|chieu nay|toi nay|"
            r"hom qua|truoc day|gia su|gia dinh|neu|co nen|nen|co the|nong|lanh|"
            r"mua|co bao|con bao|bao lon|toc do gio|huong gio|gio manh|nang|benh|mang thai)\b|\b(ngay|tuan|thang|nam) (sau|truoc|toi)\b"
            r"|\b(gio|phut|ngay) nua\b|\b\d+[/-]\d+\b|\b\d+(?:[.,]\d+)?\s*(?:°|do c|%)", question):
        return None
    location = (snapshot or {}).get("DiaDiem") or get_location()
    if _mentions_other_location(message, location):
        requested=named_location(message)
        if requested is None:
            return 'Bạn muốn xem thời tiết ở địa điểm nào trước?'
        start=local_now().replace(minute=0,second=0,microsecond=0)
        try:
            values=forecast_weather(get_weather_data(requested),(start,start+timedelta(hours=1)),fields)
        except WeatherDataUnavailable:
            values={}
        if not values:
            return "Mình chưa có số liệu thời tiết ở địa điểm bạn hỏi. Bạn chọn địa điểm đó trên bảng giám sát giúp mình nhé."
        parts=[]
        if 'NhietDo' in values:parts.append(f"nhiệt độ {values['NhietDo'][0]:g} °C")
        if 'DoAm' in values:parts.append(f"độ ẩm {values['DoAm'][0]:g}%")
        return f"Theo mô hình Open-Meteo, {requested['Ten']} lúc {start:%H:%M}: "+', '.join(parts)+'.'
    readings = (snapshot or {}).get("DuLieu") or {}
    if (snapshot or {}).get("DuLieuCu") or (snapshot or {}).get("ThoiTietCu"):
        stamp = str(snapshot.get("ThoiGianThoiTiet") or snapshot.get("ThoiGian") or "chưa rõ")[:16].replace("T", " ")
        return f"Số liệu thời tiết ở {location['Ten']} đã cũ (cập nhật {stamp}). Bạn cập nhật lại để mình xem tình hình hiện tại nhé."
    temperature = _reading(readings.get("NhietDo"), nonnegative=False)
    humidity = _reading(readings.get("DoAm"))
    if humidity is not None and humidity > 100:
        humidity = None
    if fields == ("NhietDo",):
        return (f"Ở {location['Ten']} hiện là {temperature:g} °C." if temperature is not None
                else f"Mình chưa có số đo nhiệt độ ở {location['Ten']}.")
    if fields == ("DoAm",):
        return (f"Độ ẩm ở {location['Ten']} hiện là {humidity:g}%." if humidity is not None
                else f"Mình chưa có số đo độ ẩm ở {location['Ten']}.")
    values = []
    if temperature is not None:
        values.append(f"{temperature:g} °C")
    if humidity is not None:
        values.append(f"độ ẩm {humidity:g}%")
    return (f"Ở {location['Ten']} hiện " + ", ".join(values) + "." if values
            else f"Mình chưa có số liệu thời tiết ở {location['Ten']}.")


def _weather_forecast_topic(message, history=()):
    if not future_period(message):
        return None
    question = _plain_question(message)
    if re.search(r"\b(gia su|gia dinh|neu|la gi|nghia la gi|nguyen nhan|cach|mo hinh)\b", question):
        return None
    weather = r"\b(thoi tiet|nhiet do|bao nhieu do|do am|weather|temperature|humidity)\b"
    air = r"\b(aqi|khong khi|bui|pm\s*2[.,]?\s*5|pm\s*10)\b"
    if re.search(air, question):
        return None
    if re.search(weather, question):
        return message
    if not is_followup_question(message) or is_activity_question(message):
        return None
    for turn in reversed(history):
        if turn.get('role') != 'user' or social_intent(turn['content']):
            continue
        previous = _plain_question(turn['content'])
        if re.search(weather, previous) and not re.search(air, previous):
            return turn['content']
        if not is_followup_question(turn['content']):
            break
    return None


def _weather_forecast_reply(message, history, snapshot):
    topic = _weather_forecast_topic(message, history)
    if topic is None:
        return None
    period = future_period(message)
    window = forecast_window(message)
    if window is None:
        return 'Mình có thể xem dự báo thời tiết trong 5 ngày tới. Bạn muốn xem ngày nào?'
    location = (snapshot or {}).get('DiaDiem') or get_location()
    if _mentions_other_location(topic,location) and named_location(topic) is None:
        return 'Bạn muốn xem dự báo thời tiết ở địa điểm nào trước?'
    location=named_location(topic) or location
    query = _plain_question(topic)
    fields = []
    if re.search(r'\b(nhiet do|bao nhieu do|temperature)\b', query):
        fields.append('NhietDo')
    if re.search(r'\b(do am|humidity)\b', query):
        fields.append('DoAm')
    fields = fields or ['NhietDo', 'DoAm']
    try:
        values = forecast_weather(get_weather_data(location), window, fields)
    except WeatherDataUnavailable:
        values = {}
    if not values:
        return f'Mình chưa lấy được đầy đủ dự báo thời tiết {period} ở {location["Ten"]}. Bạn thử lại sau nhé.'
    parts = []
    for field, label, unit in [('NhietDo', 'nhiệt độ', ' °C'), ('DoAm', 'độ ẩm', '%')]:
        if field in values:
            low, high = min(values[field]), max(values[field])
            value = f'{low:g}' if low == high else f'{low:g}–{high:g}'
            parts.append(f'{label} khoảng {value}{unit}')
    start, end = window
    date = start.strftime('%d/%m')
    if (end - start).total_seconds() < 24 * 3600:
        date += f', {start:%H:%M}–{end:%H:%M}'
    return f'Theo dự báo Open-Meteo, {location["Ten"]} {period} ({date}): ' + ', '.join(parts) + '.'


def _combined_conditions_reply(message, history, snapshot):
    """A choice of both topics must return both, using the same time and place."""
    if topic_kinds(message) != ("weather", "air") or _wants_detail(message, history):
        return None
    if re.search(r"\b(gia su|gia dinh|neu|la gi|nghia la gi|cach|tai sao|vi sao|so sanh)\b",
                 _plain_question(message)):
        return None
    weather = single_topic_question(message, "weather")
    air = single_topic_question(message, "air")
    if future_period(message):
        replies = (_weather_forecast_reply(weather, (), snapshot),
                   _air_forecast_reply(air, (), snapshot))
    else:
        replies = (_weather_reply(weather, (), snapshot), _grounded_reply(air, (), snapshot))
    if all(reply is not None for reply in replies):
        return "\n".join(replies)
    return None


def _air_forecast_reply(message, history, snapshot):
    """Use actual hourly air forecasts, never today's AQI as tomorrow's value."""
    period = future_period(message)
    if not period:
        return None
    question = _plain_question(message)
    if re.search(r"\b(gia su|gia dinh|neu|la gi|nghia la gi|cach|phuong phap|mo hinh|nguyen ly)\b", question):
        return None
    air_topic = r"\b(aqi|khong khi|air quality|pm\s*2[.,]?\s*5|pm\s*10|bui min|khoi bui)\b"
    topic = message
    # A short 'còn mai?' inherits only user context, never a bot's stray claim.
    if not re.search(air_topic, question) and not is_activity_question(message, history):
        if not is_followup_question(message):
            return None
        for turn in reversed(history):
            if turn.get("role") != "user":
                continue
            if social_intent(turn["content"]):
                continue
            topic = turn["content"]
            previous = _plain_question(topic)
            if re.search(air_topic, previous) or is_activity_question(topic):
                break
            if not is_followup_question(topic):
                return None
        else:
            return None
    elif re.search(r"\b(thoi tiet|nhiet do|mua|nong|lanh|gio manh|nang)\b", question) and not re.search(air_topic, question):
        return None
    location = (snapshot or {}).get("DiaDiem") or get_location()
    # Honor an explicitly named forecast place without changing the dashboard.
    if _mentions_other_location(topic,location) and named_location(topic) is None:
        return 'Bạn muốn xem dự báo không khí ở địa điểm nào trước?'
    location=named_location(topic) or location
    window = forecast_window(message)
    if window is None:
        return "Mình có thể tra dự báo không khí trong khoảng 5 ngày tới. Bạn muốn xem ngày nào và vào buổi nào?"
    try:
        data = get_air_data(location)
        points = forecast_aqi(data, window)
    except AirDataUnavailable:
        points = []
    if not points:
        return (f"Mình chưa lấy được dự báo không khí {period} ở {location['Ten']}. "
                "Dữ liệu hiện tại không đủ để kết luận cho thời điểm đó.")
    low, high = min(value for _, value in points), max(value for _, value in points)
    first=points[0][0].strftime('%H:%M')
    last=(window[1] if len(points)==1 else points[-1][0]).strftime('%H:%M')
    low_label, _ = _aqi_guidance(low)
    high_label, advice = _aqi_guidance(high)
    levels = low_label if low_label == high_label else f"{low_label} đến {high_label}"
    value = f"{low:g}" if low == high else f"{low:g}–{high:g}"
    date = points[0][0].strftime("%d/%m")
    reply = (f"Dự báo Open-Meteo/CAMS cho {location['Ten']} {period} ({date}, {first}–{last}): "
             f"US AQI khoảng {value}, mức {levels}.")
    if is_activity_question(topic, history) or re.search(r"\b(nen lam gi|tu van|khuyen|chu y)\b", question):
        reply += " " + advice
    return reply


def needs_environment_data(message, history=()):
    if clarification_reply(message, history) is not None:
        return False
    message = _dialogue_question(message, history)
    if _consultation_reply(message, history) is not None:
        return False
    if _provided_aqi_reply(message) is not None:
        return False
    if _weather_forecast_topic(message, history) is not None:
        return False  # The forecast reader is independent of saved monitoring records.
    if advice_topic(message, history):
        return False
    if concept_answer(message, history) is not None:
        return False
    if social_intent(message) or assistant_help_intent(message) or not is_environment_question(message, history):
        return False
    fields = _requested_fields(message, history)
    return fields is None or bool(fields) or bool(future_period(message))


def needs_air_data(message, history=()):
    if clarification_reply(message, history) is not None:
        return False
    message = _dialogue_question(message, history)
    if not needs_environment_data(message, history):
        return False
    fields = _requested_fields(message, history)
    return (fields is None or bool(set(fields) & {"US_AQI", "PM25", "PM10"})
            or bool(future_period(message) and
                    (is_activity_question(message, history) or re.search(
                        r"\b(aqi|khong khi|bui|pm)\b", _plain_question(message)))))


def _social_reply(message, history):
    intent = social_intent(message)
    if not intent:
        return None
    if intent == "clarify":
        if is_environment_question(message, history):
            return None  # Let the knowledge-backed explanation use the previous topic.
    return {
        "greeting": "Chào bạn, mình là Xanh Non. Bạn muốn xem tình hình môi trường hay cần tư vấn hoạt động ngoài trời?",
        "thanks": "Không có gì nhé!",
        "goodbye": "Tạm biệt bạn, hẹn gặp lại nhé!",
        "acknowledge": "Ừ, cần hỏi thêm điều gì bạn cứ nhắn nhé.",
        "attention": "Mình đây, bạn muốn hỏi gì nào?",
        "clarify": "Bạn chưa rõ phần nào? Gửi lại ý đó, mình sẽ giải thích dễ hiểu hơn nhé.",
        "correction": "Bạn chỉ giúp mình chỗ nào chưa đúng nhé. Mình sẽ kiểm tra lại theo dữ liệu và nguồn tham chiếu.",
        "help": "Bạn muốn mình tư vấn về chất lượng không khí, hoạt động ngoài trời hay tiếng ồn?",
    }[intent]


def _consultation_stage(history):
    if not history or history[-1].get("role") != "assistant":
        return None
    # An acknowledgment or attention check does not answer the pending question.
    for index in range(len(history)-2,-1,-2):
        if social_intent(history[index]['content']):
            continue
        last=_plain_question(history[index+1]['content'])
        break
    else:
        return None
    if "chat luong khong khi hien tai truoc" in last and "ban muon" in last:
        return "offer_current"
    if re.search(r"\bban (?:du dinh|dinh|muon|tinh)\b.{0,100}\b(thoi diem nao|luc nao|may gio|ngay nao|hom nay|hom khac|hom nao)\b", last):
        return "ask_time"
    return None


_FOLLOWUP_READINGS = (
    (r'\b(thoi tiet|weather)\b', 'Thời tiết'),
    (r'\b(nhiet do|bao nhieu do|temperature)\b', 'Nhiệt độ'),
    (r'\b(do am|humidity)\b', 'Độ ẩm'),
    (r'\b(chat luong khong khi|o nhiem khong khi|khong khi|us aqi|aqi|air quality)\b', 'US AQI'),
)


def _reading_followup_label(message):
    """Only a short request for readings can reuse an earlier place and time."""
    if invalid_clock(message):
        return None
    text = without_clock(message) if explicit_clock(message) else message
    text = strip_time_references(without_locations(text))
    labels = []
    for pattern, label in _FOLLOWUP_READINGS:
        if re.search(pattern, text):
            labels.append(label)
            text = re.sub(pattern, ' ', text)
    text = ' '.join(text.split())
    fillers = (r'(?:(?:nhu the nao|the nao|ra sao|thi sao|bao nhieu|doi sang|chuyen sang|'
               r'giup minh|giup toi|cho minh|cho toi|xem them|xem|con|the|vay|va|voi|'
               r'cung|o|tai|luc|vao|khoang|nhe|nhi|ban|a)\s*)*')
    return ' và '.join(labels) if labels and re.fullmatch(fillers, text) else None


def _reading_followup_question(message, history):
    if not history:
        return None
    label = _reading_followup_label(message)
    if label is None:
        return None
    _, mentions = location_mentions(message)
    if len({place['MaDiaDiem'] for _, _, place in mentions}) > 1:
        return None
    for index in range(len(history) - 1, -1, -1):
        turn = history[index]
        if turn.get('role') != 'user' or social_intent(turn['content']):
            continue
        previous = _dialogue_question(turn['content'], history[:index])
        prior_text = _plain_question(without_locations(
            without_clock(previous) if explicit_clock(previous) else previous))
        # Hypotheses, definitions and historical questions are not live readings.
        if (re.search(r'\b(gia su|gia dinh|neu|vi du|minh hoa|la gi|nghia la gi|'
                      r'tai sao|vi sao|cach|so sanh|hom qua|lich su|truoc day)\b',
                      prior_text)
                or re.search(r'\b(?:us aqi|aqi|nhiet do|do am)\s*'
                             r'(?:(?:la|len|bang|o muc|=|:)\s*)?-?\d', prior_text)
                or not (topic_kinds(previous) or is_activity_question(previous))
                or (_requested_fields(previous, history[:index]) == () and not future_period(previous))):
            return None
        _, old_mentions = location_mentions(previous)
        if len({place['MaDiaDiem'] for _, _, place in old_mentions}) > 1:
            return None
        place = named_location(message) or named_location(previous)
        question = _plain_question(message)
        now_requested = bool(re.search(r'\b(bay gio|hien tai|luc nay)\b', question))
        period = None if now_requested else future_period(message)
        if not period and not now_requested:
            period = ('hôm nay' if re.search(r'\bhom nay\b', question)
                      else future_period(previous))
        clock = None if now_requested else explicit_clock(message) or explicit_clock(previous)
        resolved = label + (' tại ' + place['Ten'] if place else '')
        if period:
            resolved += ' ' + period
        if clock:
            resolved += ' lúc ' + clock_label(clock)
        if now_requested:
            resolved += ' hiện tại'
        return resolved
    return None


def _dialogue_question(message, history):
    """Resolve short answers using user topics, never old assistant measurements."""
    message = resolve_topic_choice(message, history)
    reading = _reading_followup_question(message, history)
    if reading is not None:
        return reading
    place=location_followup(message)
    if place is not None:
        for index in range(len(history)-1,-1,-1):
            if history[index].get('role')!='user' or social_intent(history[index]['content']):
                continue
            previous=_dialogue_question(history[index]['content'],history[:index])
            if ((topic_kinds(previous) or is_activity_question(previous))
                    and (_requested_fields(previous,history[:index])!=() or future_period(previous))):
                clock=explicit_clock(previous)
                resolved=without_locations(without_clock(previous) if clock else previous)+' tại '+place['Ten']
                if clock:
                    resolved+=' lúc '+clock_label(clock)
                return resolved
            break
    question = _plain_question(message).strip(" .?!")
    affirmative = (_consultation_stage(history) == "offer_current"
                   and re.fullmatch(r"(?:(?:duoc|ok|oke|okay|vang|da|u|uh)|(?:xem|xem luon|co)(?: nhe)?)(?: (?:nhe|ban|a))?", question))
    current = current_time_reply(message) or bool(affirmative)
    brief = brief_reply_request(message)
    time_followup = is_time_followup(message)
    if not current and not brief and not time_followup:
        return message
    for index in range(len(history) - 1, -1, -1):
        turn = history[index]
        if turn.get("role") != "user":
            continue
        if social_intent(turn['content']):
            continue
        previous = _dialogue_question(turn["content"], history[:index])
        if social_intent(previous):
            continue
        if is_followup_question(previous):
            continue
        if is_environment_question(previous, history[:index]):
            if brief:
                return previous + " Trả lời ngắn gọn."
            # Both forecast readers and the API's data selection use this same question.
            old_clock=explicit_clock(previous)
            new_clock=explicit_clock(message)
            text=without_clock(previous) if old_clock else previous
            now_requested=bool(re.search(r'\b(bay gio|hien tai|luc nay)\b',question))
            clock_only=bool(new_clock and not future_period(message)
                            and not re.search(r'\bhom nay\b',question))
            if not clock_only:
                text=strip_time_references(text)
            if old_clock and not new_clock and not now_requested:
                text+=' lúc '+clock_label(old_clock)
            timeframe = message if time_followup else ("Hôm nay" if "hom nay" in question else "Bây giờ")
            return text + " " + timeframe
        break
    return message


def _consultation_reply(message, history):
    """Ask one useful question when a consultation has not specified its time."""
    question = _plain_question(message).strip(" .?!")
    clock = explicit_clock(message)
    if (clock and not future_period(message) and _reading_followup_label(message)
            and not re.search(r'\b(hom nay|hien tai|bay gio|luc nay)\b', question)):
        return f'Bạn muốn xem lúc {clock_label(clock)} hôm nay hay ngày nào khác?'
    if invalid_clock(message) and is_activity_question(message) and re.search(r'\b(muon|du dinh|tu van)\b',question):
        return 'Bạn cho mình giờ hợp lệ từ 00:00 đến 23:59 nhé.'
    if (_consultation_stage(history)=='ask_time'
            and re.search(r'\b(vi sao|tai sao|ly do|de lam gi|de phuc vu|lien quan gi)\b',question)
            and re.search(r'\b(ban hoi|ban muon biet|ban can biet|viec hoi|cau hoi|hoi (?:gio|ngay|thoi diem|thoi gian))\b',question)):
        return 'Mình hỏi để xem số đo hoặc dự báo đúng thời điểm bạn định vận động.'
    if (is_activity_question(message) and re.search(r"\b(tu van|muon|du dinh|len ke hoach)\b", question)
            and not future_period(message)
            and not re.search(r"\b(hom nay|hien tai|bay gio|luc nay|gio luon|sang|chieu|buoi toi|toi nay|khi|neu|gia su|gia dinh|benh|hen|kho tho)\b", question)):
        clock=explicit_clock(message)
        if clock:
            return f'Bạn muốn xem lúc {clock_label(clock)} hôm nay hay ngày nào khác?'
        return "Bạn định vận động hôm nay hay vào thời điểm nào khác?"
    if not history or history[-1].get("role") != "assistant":
        return None
    invitation = _plain_question(history[-1]["content"])
    question = _plain_question(message).strip(" .?!")
    stage = _consultation_stage(history)
    if stage == "ask_time":
        if uncertain_reply(message):
            return "Nếu chưa chốt giờ, mình có thể xem chất lượng không khí hiện tại trước. Bạn muốn xem luôn không?"
        if social_intent(message) == "clarify":
            return "Mình muốn biết bạn định tập lúc nào, chẳng hạn bây giờ hoặc sáng mai, để xem đúng chất lượng không khí lúc đó."
    if stage == "offer_current" and re.fullmatch(r"(?:khong|khong can|chua|de sau|thoi)(?: (?:nhe|ban|a))?", question):
        return "Được, khi nào bạn chốt thời điểm thì nhắn mình nhé."
    if (not re.search(r"\bban muon\b", invitation)
            or not re.search(r"\b(tu van|hoat dong ngoai troi)\b", invitation)
            or not is_activity_question(message)
            or future_period(message)
            or re.search(r"\b(hom nay|bay gio|luc nay|hien tai|ngay|gio|sang|chieu|toi)\b", question)):
        return None
    activity = re.fullmatch(r"(?:(?:minh|toi) (?:muon|dinh|tinh|du dinh) )?(?:di )?"
                            r"(chay bo|di bo|di dao|dap xe|tap the duc)(?: (?:nhe|thoi|nha|ban|a))*", question)
    if activity:
        label = {"chay bo": "chạy bộ", "di bo": "đi bộ", "di dao": "đi dạo", "dap xe": "đạp xe", "tap the duc": "tập thể dục"}[activity[1]]
        return f"Bạn định {label} bây giờ hay vào thời điểm nào? Mình sẽ xem chất lượng không khí lúc đó để tư vấn."
    return None


def _grounded_reply(message, history, snapshot):
    """Answer short outdoor/AQI questions from verified readings without model guesses."""
    if _wants_detail(message, history):
        return None
    question = _plain_question(without_locations(message))
    definitions = {
        "aqi": "AQI là chỉ số thể hiện mức ô nhiễm không khí và mức độ ảnh hưởng tới sức khỏe. Chỉ số càng cao thì mức lo ngại càng lớn; ứng dụng này dùng thang US AQI.",
        "pm2.5": "PM2.5 là các hạt bụi mịn có đường kính từ 2,5 micromet trở xuống. Chúng có thể đi sâu vào phổi và ảnh hưởng đến hệ hô hấp, tim mạch.",
        "pm10": "PM10 là các hạt bụi có đường kính từ 10 micromet trở xuống. Bụi này có thể đi vào đường hô hấp và ảnh hưởng tới sức khỏe.",
    }
    for term, definition in definitions.items():
        if re.fullmatch(r"(?:cho (?:minh|toi) (?:hoi|biet) )?" + re.escape(term) + r"\s+(?:la gi|nghia la gi)[?.!\s]*", question):
            return definition
    hypothetical = re.search(r"\b(gia su|gia dinh|neu)\b", question)
    given_aqi = re.search(r"\b(?:us\s+)?aqi\s*(?:(?:la|len|o muc|bang)\s*)?(\d+(?:[.,]\d+)?)\b", question)
    if hypothetical and given_aqi and re.search(r"\b(ra ngoai|ngoai troi|chay bo|di dao|dap xe)\b", question):
        if not re.search(r"\b(thoi tiet|nhiet do|mua|nong|lanh|benh|mang thai|hen|kho tho|dau nguc)\b", question):
            value = float(given_aqi[1].replace(",", "."))
            if 0 <= value <= 500:
                category, advice = _aqi_guidance(value)
                return f"US AQI {value:g} thuộc mức {category}. {advice}"
    if future_period(message):
        return None
    activity = r"(ra ngoai|ngoai troi|di dao|chay bo|tap the duc|dap xe)"
    outdoor = bool(is_activity_question(message, history)
                   or re.search(r"\b(co nen|nen|co the|co can han che)\b.{0,30}" + activity, question)
                   or re.search(activity + r".{0,25}\b(duoc khong|duoc ko|dc ko|co an toan|on khong)\b", question))
    current_aqi = bool(re.search(r"\b(aqi|chat luong khong khi|khong khi)\b", question)
                       and re.search(r"\b(hien tai|bay gio|luc nay|hom nay|dang|bao nhieu|the nao|tot khong|xau khong|co du lieu|co so lieu|doc duoc|xem duoc)\b", question))
    conditional = re.search(r"\bkhi\b", re.sub(r"\bkhong khi\b", "", question))
    # These questions need an explanation or weather/personal context, not just AQI.
    if (not outdoor and not current_aqi) or conditional or re.search(
            r"\b(la gi|vi sao|tai sao|cach tinh|khau trang|mua|co bao|troi bao|bao lon|nhiet do|nong|lanh|nang|thoi tiet|mang thai|hen|benh|bi|om|sot|kho tho|dau nguc|chong mat|nhuc dau|buon non|met moi|trong nha|phong tap|du bao|ngay mai|ngay kia|tuan toi|cuoi tuan|chieu nay|toi nay|hom qua|truoc day|luc truoc|sau nay|gia su|gia dinh|neu)\b"
            r"|\b(ngay|tuan|thang|nam) (sau|truoc|toi)\b|\b(gio|phut|ngay) nua\b"
            r"|\baqi\s*(la|=|:)?\s*\d|\b\d+[/-]\d+\b", question):
        return None
    if outdoor and re.search(r"\b(cach|loi ich|tac dung|ky thuat|huong dan|so sanh|o dau|cho nao|cong vien nao)\b", question):
        return None
    location = (snapshot or {}).get("DiaDiem") or get_location()
    # An explicitly named other place must not inherit the selected place's AQI.
    if _mentions_other_location(message, location):
        requested=named_location(message)
        if requested is None:
            return 'Bạn muốn xem chất lượng không khí ở địa điểm nào trước?'
        try:
            data=get_air_data(requested)
            current=data.get('current',{})
            value=_reading(current.get('us_aqi'))
        except AirDataUnavailable:
            value=None
        if value is None:
            return f'Mình chưa lấy được US AQI hợp lệ ở {requested["Ten"]}, nên chưa đánh giá được chất lượng không khí tại đó.'
        other={'DiaDiem':requested,'ThoiGian':data.get('LayLuc'),
               'DuLieu':{'US_AQI':value,'PM25':current.get('pm2_5'),'PM10':current.get('pm10')}}
        return _grounded_reply(message,history,other)
    readings = (snapshot or {}).get("DuLieu") or {}
    aqi = _reading(readings.get("US_AQI"))
    if aqi is None:
        if is_activity_suggestion(message, history):
            return (f"Mình chưa có AQI ở {location['Ten']} nên chưa đủ dữ liệu để gợi ý hoạt động theo chất lượng không khí. "
                    "Bạn cập nhật dữ liệu giúp mình nhé.")
        return (f"Chưa có US AQI hợp lệ tại {location['Ten']}, nên mình chưa đủ dữ liệu để đánh giá không khí"
                + (" và khuyên có nên ra ngoài. " if outdoor else ". ")
                + "Bạn hãy cập nhật bảng giám sát trước.")
    category, advice = _aqi_guidance(aqi)
    if (snapshot or {}).get("DuLieuCu"):
        stamp = str(snapshot.get("ThoiGian", "chưa rõ"))[:16].replace("T", " ")
        return (f"US AQI ở {location['Ten']} lần cập nhật gần nhất ({stamp}) là {aqi:g} ({category}). "
                "Số liệu này đã cũ; bạn cập nhật lại trước khi quyết định hoạt động ngoài trời nhé.")
    reading = f"US AQI ở {location['Ten']} hiện là {aqi:g} ({category})"
    if not outdoor:
        return f"{reading}."
    if (not is_activity_suggestion(message, history)
            and re.search(r"\b(ngan gon|ngan hon|gon hon|rut gon|tom tat)\b", question)):
        return f"{reading}. {advice}"
    if is_activity_suggestion(message, history):
        if aqi <= 100:
            suggestion = "Xét riêng chất lượng không khí, bạn có thể đi bộ, đi dạo hoặc đạp xe nhẹ."
            if aqi > 50:
                suggestion += " Người nhạy cảm nên giảm thời gian và cường độ hoạt động."
        elif aqi <= 150:
            suggestion = "Bạn có thể chọn đi dạo hoặc vận động nhẹ; nhóm nhạy cảm nên giảm thời gian và cường độ hoạt động ngoài trời."
        else:
            suggestion = "Bạn nên ưu tiên đọc sách hoặc vận động nhẹ trong nhà, hạn chế hoạt động ngoài trời kéo dài hay gắng sức."
            if aqi > 200:
                suggestion = "Bạn nên ưu tiên hoạt động trong nhà như đọc sách, nghỉ ngơi; tránh vận động ngoài trời kéo dài hoặc gắng sức."
            if aqi > 300:
                suggestion = "Bạn nên ở trong nhà và tránh hoạt động thể chất ngoài trời."
        return f"{reading}. {suggestion}"
    if aqi <= 100:
        return f"Xét về chất lượng không khí, bạn có thể ra ngoài: {reading}." + (
            " Người nhạy cảm nên giảm thời gian và cường độ hoạt động." if aqi > 50 else "")
    if aqi <= 150:
        return f"{reading}. Bạn có thể ra ngoài, nhưng nhóm nhạy cảm nên giảm thời gian và cường độ hoạt động."
    if aqi <= 200:
        return (f"Bạn nên giảm thời gian ở ngoài và tránh vận động gắng sức: {reading}. "
                "Nếu thuộc nhóm nhạy cảm, nên chuyển hoạt động kéo dài hoặc gắng sức vào trong nhà.")
    if aqi <= 300:
        return (f"Bạn nên hạn chế ra ngoài: {reading}. "
                "Tránh hoạt động kéo dài hoặc gắng sức; nhóm nhạy cảm nên tránh hoạt động thể chất ngoài trời.")
    return f"Bạn nên hạn chế ra ngoài: {reading}. {advice}"


def _reference_context(message):
    """Small source-backed context for explanations, not invented clinical claims."""
    question = _plain_question(message)
    if "pm2.5" in question or "pm10" in question or "bui min" in question:
        return (
            "Kiến thức tham chiếu EPA: PM2.5 là hạt bụi đường kính từ 2,5 micromet trở xuống; "
            "PM10 từ 10 micromet trở xuống. Bụi có thể đi sâu vào phổi; bụi mịn có thể ảnh hưởng "
            "hệ hô hấp và tim mạch. Nguồn gồm khói đốt, giao thông, công nghiệp và các hạt hình thành "
            "trong khí quyển. Nồng độ bụi có đơn vị µg/m³, không phải giá trị AQI. Khi không khí ô nhiễm, "
            "giảm thời gian và cường độ hoạt động ngoài trời theo mức AQI.\n"
        )
    return ""


def _generate(message, history, snapshot, on_text=None, cancelled=None):
    output = ReplyFilter(on_text)
    result = _generate_raw(message, history, snapshot,
                           output.feed if on_text is not None else None, cancelled)
    if not output.received:
        output.feed(result["reply"])
    reply = output.finish()
    return {**result, "reply": reply,
            "truncated": bool(result.get("truncated") or has_dangling_intro(reply))}


def _conversation_reply(message, history, detailed=False, on_text=None, cancelled=None):
    """Let the model handle general conversation without injecting dashboard data."""
    style = "Giải thích rõ, vừa đủ." if detailed else "Trả lời trực tiếp trong 1–3 câu ngắn."
    prompt = (
        "Bạn là Xanh Non. Trò chuyện bằng tiếng Việt tự nhiên, xưng mình và gọi người dùng là bạn. "
        + style + " Tập trung vào câu hỏi hiện tại và giữ ngữ cảnh còn liên quan. "
        "Khi người dùng đổi chủ đề, trả lời theo chủ đề mới. "
        "Không tự giới thiệu lại hoặc lặp lời chào khi người dùng không hỏi về bạn. "
        "Nếu câu hỏi chưa rõ, hỏi lại một câu cụ thể. Nếu không biết, nói rõ, không đoán. "
        "Không tự thêm chỉ số môi trường, thông báo thiếu dữ liệu hoặc lời khuyên không liên quan. "
        "Không chẩn đoán bệnh, kê thuốc hoặc đưa ra quyết định tài chính thay người dùng."
    )
    history = [{**turn, "content": clean_reply(turn["content"])}
               if turn["role"] == "assistant" else turn for turn in history]
    messages = [{"role": "system", "content": prompt}] + history + [{"role": "user", "content": message}]
    limit = (-1 if MAX_NEW_TOKENS == -1 else
             max(MAX_NEW_TOKENS, DETAIL_MAX_NEW_TOKENS) if detailed else MAX_NEW_TOKENS)
    return _model_reply(messages, limit, on_text, cancelled)


def _generate_raw(message, history, snapshot, on_text=None, cancelled=None):
    consultation = clarification_reply(message, history)
    if consultation is None:
        message = _dialogue_question(message, history)
        consultation = _consultation_reply(message, history)
    if consultation is not None:
        if on_text is not None and (cancelled is None or not cancelled.is_set()):
            on_text(consultation)
        return {"reply": consultation, "truncated": False}
    detailed = _wants_detail(message, history)
    help_intent = assistant_help_intent(message)
    social = _social_reply(message, history)
    if social is not None:
        grounded = social
    elif help_intent:
        grounded = {
            "identity": "Mình là Xanh Non, trợ lý môi trường của ứng dụng. Mình giúp bạn hiểu các chỉ số và chọn hoạt động phù hợp với chất lượng không khí.",
            "capabilities": "Mình có thể đọc và giải thích AQI, bụi mịn, nhiệt độ, độ ẩm, tiếng ồn ở địa điểm bạn chọn, rồi gợi ý hoạt động phù hợp với chất lượng không khí. Bạn muốn xem tình hình hiện tại hay tìm hiểu chỉ số nào?",
            "features": "Ứng dụng giúp bạn xem các chỉ số môi trường, bản đồ chất lượng không khí, xu hướng dữ liệu và cảnh báo theo địa điểm. Mình hỗ trợ giải thích các chỉ số và gợi ý hoạt động phù hợp với chất lượng không khí.",
            "guide": "Bạn chọn địa điểm rồi nhấn Cập nhật dữ liệu để xem các chỉ số mới nhất. Sau đó có thể xem bản đồ, xu hướng, cảnh báo hoặc hỏi mình về chỉ số bạn quan tâm.",
        }[help_intent]
    elif not is_environment_question(message, history):
        return _conversation_reply(message, history, detailed, on_text, cancelled)
    else:
        grounded = _provided_aqi_reply(message)
        if grounded is None:
            grounded = _combined_conditions_reply(message, history, snapshot)
        if grounded is None:
            grounded = _weather_forecast_reply(message, history, snapshot)
        if grounded is None:
            grounded = _air_forecast_reply(message, history, snapshot)
        if grounded is None:
            grounded = practical_answer(message, history, detailed)
        if grounded is None:
            grounded = None if detailed or history else exact_answer(message)
        if grounded is None:
            grounded = concept_answer(message, history, detailed=detailed)
        if grounded is None:
            grounded = _weather_reply(message, history, snapshot)
        if grounded is None:
            grounded = _grounded_reply(message, history, snapshot)
    if grounded is not None:
        if on_text is not None and (cancelled is None or not cancelled.is_set()):
            on_text(grounded)
        return {"reply": grounded, "truncated": False}
    max_tokens = (-1 if MAX_NEW_TOKENS == -1 else
                  max(MAX_NEW_TOKENS, DETAIL_MAX_NEW_TOKENS) if detailed else MAX_NEW_TOKENS)
    # Old replies can contain copied instructions; keep them out of future turns.
    history = [{**item, "content": clean_reply(item["content"])} if item["role"] == "assistant" else item
               for item in history]
    if MODEL_PROMPT_PROFILE in {'grounded-v15','grounded-v16'}:
        if MODEL_PROMPT_PROFILE == 'grounded-v16':
            from chat_briefing_v16 import compact_messages
        else:
            from chat_briefing_v15 import compact_messages
        messages = compact_messages(message, history, snapshot)
    else:
        selected_fields = _requested_fields(message, history)
        weather_only = bool(selected_fields) and set(selected_fields) <= {"NhietDo", "DoAm"}
        current_question = (
            f"Dữ liệu bảng giám sát do ứng dụng cung cấp:\n{_dashboard_context(snapshot, selected_fields)}\n\n"
            + ("" if weather_only else (reference_context(message, history) or _reference_context(message)))
            + f"Câu hỏi của người dùng:\n{message}"
        )
        messages = [{"role": "system", "content": _system_prompt(snapshot, detailed, selected_fields)}] + history + [
            {"role": "user", "content": current_question}
        ]
    return _model_reply(messages, max_tokens, on_text, cancelled)


def _model_reply(messages, max_tokens, on_text=None, cancelled=None):
    runtime = _load_runtime()
    if isinstance(runtime, NativeChatbot):
        return runtime.generate(messages, max_tokens, on_text, cancelled)
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
    block_size = max_tokens if max_tokens > 0 else 2048
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
            if (int(new_tokens[-1]) in end_tokens or max_tokens > 0
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
        except ChatbotBusy as exc:
            queue.put({"type": "error", "loi": str(exc)})
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
