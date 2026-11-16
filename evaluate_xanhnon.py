"""Compare real GGUF generations on a fixed set kept outside SFT training."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import time
from unittest.mock import patch

import chatbot
from chat_knowledge import normalized, reference_context
from chat_output import clean_reply, has_dangling_intro
from location_catalog import get_location
from native_chatbot import NativeChatbot


ROOT = Path(__file__).resolve().parent
ASSESSMENT_VERSION = 9
CASES = [
    {"id": "explain_aqi", "question": "Bạn giải thích AQI kiểu dễ hiểu cho mình được không?",
     "required_any": [["AQI"], ["không khí", "ô nhiễm"]], "forbidden": ["175", "45.4"]},
    {"id": "fine_particles", "question": "PM2.5 nhỏ tới mức nào và có vào phổi được không?",
     "required_any": [["2,5", "2.5"], ["phổi"]], "forbidden": ["45.4", "thấp hơn mức an toàn", "tử vong", "µg/m³"]},
    {"id": "compare_particles", "question": "PM2.5 với PM10 khác nhau ở điểm chính nào? Nói ngắn thôi.",
     "required_any": [["PM2.5"], ["PM10"], ["2,5", "2.5"], ["10"]],
     "forbidden": ["từ 10 đến 2,5", "từ 10 đến 2.5", "từ 2,5 đến 10", "từ 2.5 đến 10", "45.4"]},
    {"id": "city_particles", "question": "Trong thành phố, bụi mịn chủ yếu từ đâu tới vậy?",
     "required_any": [["bụi"], ["giao thông", "công trường", "đốt", "công nghiệp", "khí thải"]],
     "forbidden": ["45.4", "Open-Meteo"]},
    {"id": "indoor_particles", "question": "Ở trong phòng là hết lo bụi mịn rồi phải không bạn?",
     "required_any": [["bụi"], ["vẫn", "không", "có thể"], ["lọt", "khói", "bếp", "nguồn", "lọc", "từ ngoài", "bên ngoài"]],
     "forbidden": ["không thể xác định từ các chỉ số", "không thể xác định được liệu bụi", "không có thông tin về PM2.5", "Đúng vậy", "Đúng rồi"]},
    {"id": "current_weather", "question": "Cho mình xem nhanh thời tiết Hà Nội đang thế nào nhé.",
     "required_any": [["24.8", "24,8"], ["95"]],
     "forbidden": ["AQI", "PM2.5", "NoiseCapture", "tiếng ồn", "trung bình", "2026"]},
    {"id": "humidity_only", "question": "Mình muốn biết độ ẩm ở Hà Nội lúc này thôi.",
     "required_any": [["95"]], "forbidden": ["24.8", "AQI", "PM2.5", "NoiseCapture", "tiếng ồn"]},
    {"id": "unseen_weather", "question": "Thời tiết ở đây lúc này thế nào bạn nhỉ?",
     "readings": {"NhietDo": 17.3, "DoAm": 63},
     "required_any": [["17.3", "17,3"], ["63"]],
     "forbidden": ["24.8", "24,8", "95%", "AQI", "tiếng ồn"]},
    {"id": "missing_aqi", "question": "Bạn xem không khí hôm nay có ổn để mình chạy bộ không?",
     "readings": {"US_AQI": None, "PM25": 5},
     "required_any": [["chưa", "thiếu", "không có"], ["AQI", "dữ liệu"]],
     "forbidden": ["không khí tốt", "hoạt động ngoài trời bình thường", "AQI là 0"]},
    {"id": "hypothetical_aqi", "question": "Giả sử US AQI lên 175 thì nên điều chỉnh việc tập ngoài trời ra sao?",
     "readings": {"US_AQI": 42},
     "required_any": [["175"], ["Xấu"], ["giảm", "hạn chế", "tránh"]], "forbidden": ["42", "bình thường", "mức này thuộc nhóm nhạy cảm", "rất xấu", "tím"]},
    {"id": "followup", "question": "Nó có thể đi sâu tới phổi không bạn?",
     "history": [{"role": "user", "content": "PM2.5 là gì?"},
                 {"role": "assistant", "content": "PM2.5 là những hạt bụi có đường kính thường không quá 2,5 micromet."}],
     "required_any": [["phổi"], ["có thể", "có", "đi sâu"]], "forbidden": ["45.4", "chẩn đoán", "µg/m³"]},
]
COMMON_FORBIDDEN = ["Kính thưa", "Kính chúc", "trong câu hỏi của bạn", "Không tự thêm",
                    "system prompt", "chỉ báo thiếu dữ liệu khi", "các chỉ dẫn về cách trả lời",
                    "Kết luận:", "Lý do:", "giữ ấm", "kính râm", "lây nhiễm"]


def evaluation_cases(extra_path=None):
    cases = list(CASES)
    if extra_path:
        cases.extend(json.loads(Path(extra_path).read_text(encoding="utf-8")))
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Evaluation case IDs must be unique")
    fingerprint = hashlib.sha256(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return cases, fingerprint


def load_comparison(path, scope, cases):
    baseline = json.loads(Path(path).read_text(encoding="utf-8"))
    if baseline["evaluation_scope"] != scope:
        raise ValueError("Compare the same evaluation scope for both models")
    if {case["id"] for case in cases} != {case["id"] for case in baseline["cases"]}:
        raise ValueError("Compare exactly the same evaluation cases for both models")
    fingerprint = hashlib.sha256(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    if baseline.get('cases_sha256') != fingerprint or baseline.get('assessment_version') != ASSESSMENT_VERSION:
        raise ValueError('Baseline case definitions or assessment version changed; generate a fresh baseline')
    return baseline


def compare_answers(before, results, baseline_average_words):
    new_errors = {record["id"]: sorted(set(record["violations"]) - set(before[record["id"]]["violations"]))
                  for record in results}
    regressions = [record["id"] for record in results if new_errors[record["id"]]
                   or (before[record["id"]]["passed"] and not record["passed"])]
    baseline_passed = sum(record["passed"] for record in before.values())
    passed = sum(record["passed"] for record in results)
    return {"baseline_passed": baseline_passed, "candidate_passed": passed,
            "baseline_average_words": baseline_average_words, "regressions": regressions,
            "new_violations": {key: value for key, value in new_errors.items() if value},
            "eligible_for_manual_review": not regressions and passed >= baseline_passed}


def messages_for(case):
    snapshot = {"DiaDiem": get_location("hanoi"), "ThoiGian": "2026-10-19T09:00:00",
                "DuLieu": {"US_AQI": 175, "PM25": 45.4, "PM10": 60, "NhietDo": 24.8,
                           "DoAm": 95, "TiengOn": 74.99, **case.get("readings", {})}}
    question, history = case["question"], case.get("history", [])
    fields = chatbot._requested_fields(question, history)
    weather_only = bool(fields) and set(fields) <= {"NhietDo", "DoAm"}
    context = ("Dữ liệu bảng giám sát do ứng dụng cung cấp:\n"
               + chatbot._dashboard_context(snapshot, fields) + "\n\n"
               + ("" if weather_only else (reference_context(question, history) or chatbot._reference_context(question)))
               + "Câu hỏi của người dùng:\n" + question)
    return [{"role": "system", "content": chatbot._system_prompt(snapshot, False, fields)}] + history + [
        {"role": "user", "content": context}]


def assess(case, result, elapsed):
    raw = result["reply"]
    reply = clean_reply(raw)
    text = normalized(reply)
    violations = []
    for alternatives in case.get("required_any", []):
        if not any((normalized(value) in text) if normalized(value) else (value in reply) for value in alternatives):
            violations.append("missing: " + " / ".join(alternatives))
    for forbidden in COMMON_FORBIDDEN + case.get("forbidden", []):
        # A prohibited heading needs its colon. "Kết luận về ..." is ordinary
        # prose, not the mechanical "Kết luận:" heading.
        found = (bool(re.search(re.escape(forbidden[:-1]) + r"\s*:", raw, re.IGNORECASE))
                 if forbidden.endswith(":") else normalized(forbidden) in normalized(raw))
        if found:
            violations.append("unwanted: " + forbidden)
    if case.get("time_scope") == "tomorrow":
        if re.search(r"\b(hom nay|hien tai|luc nay)\b", text):
            violations.append("wrong_time_scope_for_tomorrow")
        if not re.search(r"\b(ngay mai|hom sau|ngay toi|ngay ke|ngay tiep|du bao)\b", text):
            violations.append("missing_tomorrow_or_forecast_label")
    if result["truncated"]:
        violations.append("truncated")
    if re.search(r'\b(?:nhiem_vu|chung_cu|source_ids?)\b', raw, re.IGNORECASE):
        violations.append('internal_context_label_leak')
    if has_dangling_intro(raw):
        violations.append("unfinished_intro")
    if case["id"] == "explain_aqi" and re.search(r"\b(?:chua|khong) co\b.{0,60}\b(?:du lieu|so lieu)\b", text):
        violations.append("definition_replaced_by_missing_current_data")
    if case['id'] in {'fine_particles', 'compare_particles'}:
        # Keep decimal punctuation here: normalized() removes it. A range with
        # units between its endpoints was previously a false positive.
        from chat_briefing import plain
        factual = plain(raw)
        for match in re.finditer(r'\bpm2[.,]?5\b(?P<claim>(?:(?!\bpm10\b)[^;!?\n]){0,150})', factual):
            claim = match['claim']
            if re.search(r'\btu\s+2[.,]5\s*(?:micromet(?:er)?s?|µm|μm)?\s*(?:den|toi|[-–])\s*10\b', claim):
                violations.append('incorrect_PM25_size_range_2_5_to_10')
        # Decimal full stops must not split the sentence before the range.
        if ('incorrect_PM25_size_range_2_5_to_10' not in violations
                and case['id'] == 'fine_particles' and re.search(
                r'\btu\s+2[.,]5\s*(?:micromet(?:er)?s?|µm|μm)?\s*(?:den|toi|[-–])\s*10\b', factual)):
            violations.append('incorrect_PM25_size_range_2_5_to_10')
    if case['id'] in {'fine_particles', 'followup'} and re.search(
            r'\b(?:khong|chang)\s+(?:the\s+)?(?:(?:di|hit|lot|xam nhap|qua|vao|sau|duoc)\s+){0,6}phoi\b', text):
        violations.append('incorrect_denial_of_particle_lung_penetration')
    if case["id"] == "compare_particles":
        for match in re.finditer(r"\bpm10\b(?P<prefix>(?:(?!\bpm25\b).){0,80})\b(?:lon hon|vuot qua|tren)\s+10\b", text):
            if not re.search(r"\bkhong(?:\s+\w+){0,2}\s*$", match.group("prefix")):
                violations.append("incorrect_PM10_size_above_10_micrometers")
        for match in re.finditer(r"\bpm10\b(?:(?!\bpm10\b).){0,70}\b(?:vo hai|khong anh huong(?: nhieu)? (?:den )?suc khoe)\b", text):
            before = text[max(0, match.start() - 55):match.start()]
            if not re.search(r"\b(?:khong (?:nen |the |duoc )?(?:coi|xem)|khong phai|khong co nghia)\b.{0,30}$", before):
                violations.append("unsupported_claim_PM10_harmless")
    if case["id"] == "noise_concrete_actions" or case.get("check_noise_duration"):
        for match in re.finditer(r"\btang\b.{0,70}\bthoi gian\b.{0,35}\b(?:noi on|cho on|tieng on)\b", text):
            if not re.search(r"(?:giam|han che|rut ngan) thoi gian", match.group()) and not text[max(0, match.start() - 6):match.start()].endswith("khong "):
                violations.append("unsafe_increase_noise_exposure_duration")
    if case.get('check_noise_duration') and not re.search(
            r'\b(?:giam|rut ngan|han che)\s+(?:bot\s+)?(?:thoi gian|thoi luong|buoi nghe|tiep xuc|nghe)\b'
            r'|\bnghe it(?: hon)?\b|\bkhong (?:nen )?(?:nghe|o|tiep xuc) lau\b', text):
        violations.append('missing_action_to_reduce_noise_exposure_duration')
    if case['id'] in {'balanced_greeting', 'confirmation_friendly_opening'} and not re.search(
            r'\b(?:chao|minh day|minh o day|minh san sang|ban cu hoi|duoc chu)\b', text):
        violations.append('greeting_replaced_by_echo_or_question')
    if case["id"] in ("dust_without_filter_followup", "dust_context_after_social_turn"):
        if not any(action in text for action in ("lau", "khan am", "cua")):
            violations.append("no_immediate_action_without_buying_a_filter")
    if len(reply.split()) > 85:
        violations.append("longer_than_85_words")
    return {"id": case["id"], "question": case["question"], "raw_reply": raw, "reply": reply,
            "words": len(reply.split()), "seconds": round(elapsed, 2),
            "violations": violations, "passed": not violations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--extra-cases", type=Path, help="Additional held-out consultation cases, used equally for both models")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--through-app", action="store_true", help="Evaluate the actual answer pipeline, including verified data/knowledge replies")
    args = parser.parse_args()
    scope = "application_pipeline" if args.through_app else "core_generation_without_deterministic_replies"
    try:
        cases, cases_sha256 = evaluation_cases(args.extra_cases)
        baseline = load_comparison(args.compare, scope, cases) if args.compare else None
    except ValueError as exc:
        parser.error(str(exc))
    if args.threads < 1:
        parser.error("threads must be positive")
    runtime = NativeChatbot(chatbot.NATIVE_BINARY, args.model.resolve(), args.threads, 8192, 192)
    results = []
    try:
        for case in cases:
            started = time.monotonic()
            if args.through_app:
                snapshot = {"DiaDiem": get_location("hanoi"), "ThoiGian": "2026-10-19T09:00:00",
                            "DuLieu": {"US_AQI": 175, "PM25": 45.4, "PM10": 60, "NhietDo": 24.8,
                                       "DoAm": 95, "TiengOn": 74.99, **case.get("readings", {})}}
                with patch.object(chatbot, "_load_runtime", return_value=runtime):
                    result = chatbot._generate(case["question"], case.get("history", []), snapshot)
            else:
                result = runtime.generate(messages_for(case), 192)
            record = assess(case, result, time.monotonic() - started)
            results.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)
    finally:
        runtime.close()
    report = {"model": str(args.model), "evaluation_scope": scope,
              "prompt_profile": args.prompt_profile,
              "assessment_version": ASSESSMENT_VERSION,
              "cases_sha256": cases_sha256, "inference_threads": args.threads,
              "case_count": len(results), "passed": sum(record["passed"] for record in results),
              "average_words": round(sum(record["words"] for record in results) / len(results), 1),
              "cases": results}
    if baseline:
        if baseline.get("cases_sha256") and baseline["cases_sha256"] != cases_sha256:
            parser.error("Evaluation case contents changed since the baseline")
        # Apply the same current criteria even if the baseline predates a criteria fix.
        cases_by_id = {case["id"]: case for case in cases}
        before = {record["id"]: assess(cases_by_id[record["id"]],
                  {"reply": record["raw_reply"], "truncated": "truncated" in record["violations"]},
                  record["seconds"]) for record in baseline["cases"]}
        report["comparison"] = compare_answers(before, results, baseline["average_words"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
