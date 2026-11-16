"""Clarify ambiguous short turns without guessing a topic or losing their time."""

import re

from chat_knowledge import normalized
from chat_time_context import explicit_clock, without_clock, clock_label
from chat_scope import (expand_shorthand, future_period, is_environment_question,
                        is_followup_question, is_time_followup, social_intent,
                        strip_time_references, uncertain_reply)


_TOPICS = {
    "weather": r"\b(thoi tiet|nhiet do|bao nhieu do|do am|weather|temperature|humidity)\b",
    "air": r"\b(chat luong khong khi|o nhiem khong khi|khong khi|us aqi|aqi|pm25|pm10|bui min|khoi bui|bui|air quality)\b",
}


def topic_kinds(message):
    question = expand_shorthand(normalized(message))
    return tuple(topic for topic, pattern in _TOPICS.items() if re.search(pattern, question))


def single_topic_question(message, topic):
    """Keep location/time words while removing the other topic's reading names."""
    clock = explicit_clock(message)
    question = expand_shorthand(normalized(without_clock(message) if clock else message))
    for other, pattern in _TOPICS.items():
        if other != topic:
            question = re.sub(pattern, " ", question)
    question = " ".join(question.split())
    return question + (' lúc ' + clock_label(clock) if clock else '')


def _request(message, history):
    if not is_time_followup(message):
        return None
    context = message
    for index in range(len(history) - 1, -1, -1):
        turn = history[index]
        if turn.get("role") != "user" or social_intent(turn["content"]):
            continue
        previous = resolve_topic_choice(turn["content"], history[:index])
        if is_followup_question(previous):
            continue
        # A substantive unrelated turn ends the old environmental discussion.
        if not is_environment_question(previous):
            return None
        if topic_kinds(previous) != ("weather", "air"):
            return None  # One clear topic is handled by ordinary context inheritance.
        context = previous
        break
    period = future_period(message)
    now_requested = bool(re.search(r'\b(bay gio|hien tai|luc nay)\b', normalized(message)))
    clock = None if now_requested else explicit_clock(message) or explicit_clock(context)
    if period is None and explicit_clock(message) and not now_requested:
        period = future_period(context)
    if period is None:
        period = ("hôm nay" if "hom nay" in normalized(message)
                  else "" if clock and not now_requested else "hiện tại")
    time_label = (period + (' lúc ' + clock_label(clock) if clock else '')).strip()
    return {"context": context, "period": period, "clock": clock,
            "prompt": f"Bạn muốn xem thời tiết hay chất lượng không khí {time_label}?"}


def _pending(history):
    # Recognize our own prompt together with the user request that caused it.
    # No topic or measurement is inferred from arbitrary assistant wording.
    for index in range(len(history) - 2, -1, -2):
        user, assistant = history[index:index + 2]
        if user.get("role") != "user" or assistant.get("role") != "assistant":
            return None
        if social_intent(user["content"]):
            continue
        request = _request(user["content"], history[:index])
        if request is None and uncertain_reply(user["content"]):
            request = _pending(history[:index])
        if request and normalized(assistant["content"]) == normalized(request["prompt"]):
            return request
        return None
    return None


def resolve_topic_choice(message, history):
    """Resolve a short answer only while a matching clarification is pending."""
    question = expand_shorthand(normalized(message))
    question = re.sub(r"^(?:(?:minh|toi) )?(?:(?:muon|chon|xem|hoi|can)(?: ve)? )+|^ve ", "", question)
    question = re.sub(r"(?: (?:thoi|nhe|nha|a|ban|giup minh|giup toi))+$", "", question)
    choices = {"thoi tiet": "weather", "nhiet do": "weather", "do am": "weather",
               "khong khi": "air", "chat luong khong khi": "air", "aqi": "air",
               "us aqi": "air",
               "cai dau": "weather", "cai sau": "air", "ca hai": "both", "ca 2": "both"}
    topic = choices.get(question)
    if topic is None:
        return message  # A full new question takes precedence over the pending one.
    request = _pending(history)
    if request is None:
        return message
    original = request["context"]
    context = strip_time_references(without_clock(original) if explicit_clock(original) else original)
    clock = request.get('clock')
    time_label = (request["period"] + (' lúc ' + clock_label(clock) if clock else '')).strip()
    if topic == "both":
        return "Thời tiết và chất lượng không khí " + context + " " + time_label
    context = single_topic_question(context, topic)
    if question in {"nhiet do", "do am"}:
        context = re.sub(_TOPICS[topic], " ", context)
        label = {"nhiet do": "Nhiệt độ", "do am": "Độ ẩm"}[question]
    else:
        label = "Thời tiết" if topic == "weather" else "Chất lượng không khí"
    return label + " " + context + " " + time_label


def clarification_reply(message, history):
    request = _request(message, history)
    if request:
        return request["prompt"]
    if uncertain_reply(message) or social_intent(message) == "clarify":
        request = _pending(history)
        if request:
            return request["prompt"]
    return None
