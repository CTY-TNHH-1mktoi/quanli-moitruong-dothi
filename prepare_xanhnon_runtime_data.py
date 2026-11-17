"""Prepare reviewed dialogue using the application's actual prompt structure.

All monitoring snapshots are explicitly simulated. Only the final assistant turn
is supervised, so an old answer in the supplied history is not a learning target.
The fixed generation evaluation questions remain outside this training batch.
"""

import argparse
import json
from pathlib import Path

import chatbot
from chat_knowledge import reference_context
from location_catalog import get_location
from prepare_xanhnon_data import make_record
from prepare_xanhnon_review_data import category, corrective_records, prepare
from sensor_training_data import ROOT, digest, save_json


SIMULATION_NOTICE = "Bản ghi huấn luyện: các số đo bên dưới là giả lập, không phải dữ liệu trực tiếp.\n"


def runtime_record(topic, index, question, answer, source_ids, snapshot, history=()):
    fields = chatbot._requested_fields(question, history)
    weather_only = bool(fields) and set(fields) <= {"NhietDo", "DoAm"}
    context = ("" if weather_only else (reference_context(question, history) or chatbot._reference_context(question)))
    payload = (SIMULATION_NOTICE + "Dữ liệu bảng giám sát do ứng dụng cung cấp:\n"
               + chatbot._dashboard_context(snapshot, fields) + "\n\n" + context
               + "Câu hỏi của người dùng:\n" + question)
    record = make_record(list(history) + [{"role": "user", "content": payload},
                                         {"role": "assistant", "content": answer}],
                         "environment_runtime_review", "runtime-v5:" + topic + ":" + str(index),
                         topic=topic, original_question=question, source_ids=source_ids,
                         synthetic_context=True, snapshot=snapshot,
                         supervise_last_assistant_only=True,
                         review="source_checked_facts_and_project_dialogue_policy")
    record["messages"][0]["content"] = chatbot._system_prompt(
        snapshot, chatbot._wants_detail(question, history), fields)
    return "train" if index < 6 else "validation", record


def snapshot_for(index):
    return {"DiaDiem": get_location("hanoi"), "ThoiGian": "2026-01-01T09:00:00",
            "DuLieu": {"US_AQI": [164, 181, 69, 124, 213, 47, 192, 88][index],
                       "PM25": 16 + index * 7, "PM10": 31 + index * 9,
                       "NhietDo": round(19.2 + index * 1.1, 1), "DoAm": 57 + index * 4,
                       "TiengOn": 62 + index}}


def runtime_review_records(knowledge):
    records = []
    pm_questions = [
        "Giải thích ngắn: số 2.5 và số 10 trong tên bụi chỉ điều gì?",
        "PM10 có phải chỉ những hạt đường kính trên 10 micromet không?",
        "Phân biệt giới hạn kích thước PM2.5 với PM10, nói gọn nhé.",
        "PM2.5 và PM10: nhóm nào có giới hạn kích thước nhỏ hơn?",
        "Vì sao nói PM10 là bụi kích thước tối đa 10 micromet?",
        "Mình nhầm PM10 là hạt trên 10 µm, bạn sửa giúp ngắn gọn.",
        "Nói dễ hiểu về mốc đường kính của PM2.5 và PM10 nhé.",
        "Tên PM10 và PM2.5 liên quan kích thước thế nào, trả lời ngắn nhé."]
    fresh_questions = [
        "Vậy tình hình AQI ở Hà Nội hiện giờ là bao nhiêu?",
        "Bỏ tình huống vừa nêu, AQI Hà Nội đang ở mức nào?",
        "Quay lại bảng giám sát: Hà Nội bây giờ có AQI bao nhiêu?",
        "Còn số đo không khí Hà Nội mới được cập nhật thì thế nào?",
        "Mình hỏi lại AQI hiện tại ở Hà Nội chứ không hỏi ví dụ cũ nhé.",
        "Lúc này chất lượng không khí tại Hà Nội thuộc mức gì?",
        "Đọc giúp mình AQI Hà Nội trong dữ liệu mới được cung cấp.",
        "Chuyển về Hà Nội, số AQI mới trên bảng là mấy?"]
    no_filter_questions = [
        "Mình chưa mua máy lọc được, có cách giảm bụi nào làm ngay tại nhà?",
        "Nếu chưa trang bị máy lọc thì lau dọn kiểu gì cho bớt bụi?",
        "Chưa đủ tiền mua thiết bị lọc, mình nên bắt đầu giảm bụi từ đâu?",
        "Mình không có máy lọc hay máy hút bụi, còn cách giảm bụi nào không?",
        "Chưa có máy lọc trong phòng, chỉ lau dọn thôi có cách nào phù hợp?",
        "Không mua thêm thiết bị, làm gì để hạn chế bụi vào nhà trước?",
        "Thế chưa sắm máy lọc thì mình hạn chế bụi thế nào cho đơn giản?",
        "Mình muốn giảm bụi bằng các việc không cần thiết bị lọc, bạn gợi ý nhé."]
    noise_questions = [
        "Nhà gần đường nhiều xe, cách giảm tiếp xúc tiếng ồn là gì?",
        "Để bảo vệ tai, mình có nên kéo dài thời gian nghe âm thanh lớn?",
        "Muốn hạn chế ảnh hưởng tiếng xe, cần điều chỉnh khoảng cách và thời gian ra sao?",
        "Mình đứng xa loa rồi thì có nên nghe lâu hơn không?",
        "Gần máy thi công rất ồn, nên làm gì với thời gian tiếp xúc?",
        "Muốn tai quen tiếng lớn thì ở chỗ ồn lâu có đúng không?",
        "Xe ngoài cửa ồn liên tục, bạn gợi ý các việc hạn chế tiếp xúc nhé.",
        "Giảm ảnh hưởng tiếng ồn nên đứng gần hay xa và nghe lâu hay ít?",
    ]
    for split, old in corrective_records(knowledge):
        index = int(old["group_id"].rsplit(":", 1)[-1])
        topic = old["topic"]
        snapshot = snapshot_for(index)
        question, answer = old["messages"][-2]["content"], old["messages"][-1]["content"]
        history = old["messages"][1:-2]
        if topic == "pm_size":
            question = pm_questions[index]
            answer = ("PM2.5 là hạt bụi có đường kính từ 2,5 µm trở xuống; PM10 là hạt bụi từ 10 µm trở xuống. "
                      "Đó là giới hạn kích thước, không phải nồng độ bụi.")
        elif topic == "aqi_category":
            value = [137, 151, 169, 188, 201, 231, 157, 294][index]
            question = f"Nếu giả định US AQI bằng {value}, đó là mức nào và mình nên điều chỉnh việc vận động ngoài trời thế nào?"
            label, advice = chatbot._aqi_guidance(value)
            answer = f"Theo giả định US AQI {value}, mức này là {label}. {advice}"
        elif topic == "fresh_over_history":
            question = fresh_questions[index]
            value = snapshot["DuLieu"]["US_AQI"]
            answer = f"Theo dữ liệu hiện tại được cung cấp, Hà Nội có US AQI {value}, thuộc mức {category(value)}."
        elif topic == "no_filter":
            question = no_filter_questions[index]
            answer = ("Bạn có thể lau bụi bằng khăn ẩm, hạn chế mở cửa phía đường lúc nhiều bụi và giảm khói thuốc, đốt nến trong nhà. "
                      "Những việc này không cần mua máy mới, nhưng không bảo đảm loại hết bụi mịn.")
        elif topic == "noise_duration":
            question = noise_questions[index]
            answer = ("Hãy giảm thời gian ở nơi ồn và tăng khoảng cách với nguồn ồn; nghỉ ở chỗ yên tĩnh. "
                      "Nếu phải ở nơi rất ồn, dùng nút tai hoặc chụp tai phù hợp; không nghe lâu hơn để quen tai.")
        elif topic == "pm_not_aqi":
            value = [18, 43, 62, 89, 11, 104, 56, 72][index]
            question = f"Cảm biến báo nồng độ PM2.5 là {value} µg/m³, lấy số đó làm US AQI có đúng không?"
            answer = (f"Không. {value} µg/m³ là nồng độ PM2.5, còn AQI là chỉ số quy đổi theo cách tính và thời gian lấy trung bình phù hợp. "
                      "Không lấy trực tiếp nồng độ PM2.5 làm AQI.")
        elif topic == "clarify_time":
            answer = "Mình hỏi để xem số đo hoặc dự báo đúng lúc bạn định vận động. Bạn định đi bây giờ hay vào thời điểm khác?"
        records.append(runtime_record(topic, index, question, answer, old["source_ids"], snapshot, history))

    direct_lung = [
        "Bụi PM2.5 nhỏ cỡ nào, có thể được hít sâu vào phổi chứ?",
        "Nói ngắn về đường kính PM2.5 và việc hạt này đi vào phổi nhé.",
        "Kích thước PM2.5 có nhỏ đủ để lọt sâu trong phổi không?",
        "PM2.5 mang nghĩa kích thước bao nhiêu và nó ảnh hưởng phổi thế nào?",
        "Hạt bụi nhỏ hơn 2,5 micromet có thể theo hơi thở tới phổi chứ?",
        "Vì sao PM2.5 nhỏ lại có thể được hít vào sâu trong phổi?",
        "Bạn giải thích ngắn kích thước bụi PM2.5 và khả năng vào phổi đi.",
        "PM2.5 được giới hạn đường kính ra sao, có vào phổi khi hít thở không?"]
    weather = ["Cho mình xem nhiệt độ và độ ẩm hiện tại tại Hà Nội nhé.",
               "Ở Hà Nội bây giờ thời tiết thế nào, nói thật gọn nhé.",
               "Mình chỉ cần biết Hà Nội đang nóng bao nhiêu độ và độ ẩm bao nhiêu.",
               "Cập nhật giúp nhiệt độ cùng độ ẩm tại Hà Nội lúc này.",
               "Bạn đọc nhanh nhiệt độ, độ ẩm ở địa điểm đang chọn nhé.",
               "Thời tiết hiện giờ của Hà Nội có những số liệu gì?",
               "Hà Nội hiện bao nhiêu độ và độ ẩm mấy phần trăm?",
               "Gửi mình hai số nhiệt độ và độ ẩm mới trên bảng nhé."]
    missing = ["Không khí lúc này có phù hợp để đạp xe không bạn?",
               "Đọc dữ liệu hiện tại giúp mình quyết định có đi dạo được không.",
               "Mình muốn tập ngoài trời ngay, AQI hiện tại có đủ để tư vấn không?",
               "Hôm nay dựa vào chất lượng không khí thì có nên chạy bộ?",
               "Với dữ liệu đang có, bạn kết luận không khí hiện tại tốt được chưa?",
               "Mình hỏi AQI bây giờ để chọn hoạt động ngoài trời nhé.",
               "Thiếu số AQI trên bảng thì mình có biết ra ngoài lúc này ổn không?",
               "Bảng đang không có AQI, có đủ số liệu để khuyên vận động ngoài trời không?"]
    for index in range(8):
        snapshot = snapshot_for(index)
        records.append(runtime_record("lung_direct", index, direct_lung[index],
            "PM2.5 là các hạt bụi có đường kính từ 2,5 micromet trở xuống. Chúng có thể được hít vào sâu trong phổi.",
            ["epa_pm"], snapshot))
        readings = snapshot["DuLieu"]
        records.append(runtime_record("focused_weather", index, weather[index],
            f"Hà Nội hiện {readings['NhietDo']:g} °C, độ ẩm {readings['DoAm']}%.", ["project"], snapshot))
        missing_snapshot = {**snapshot, "DuLieu": {**readings, "US_AQI": None}}
        records.append(runtime_record("missing_aqi", index, missing[index],
            "Mình chưa có US AQI hợp lệ tại Hà Nội nên chưa đủ dữ liệu để đánh giá không khí và khuyên vận động ngoài trời. Bạn cập nhật dữ liệu giúp mình nhé.",
            ["project", "airnow_aqi"], missing_snapshot))
    return records


def prepare_runtime_data(destination, sensor_dir):
    knowledge = json.loads((ROOT / "data/xanhnon/knowledge.json").read_text(encoding="utf-8"))
    generated = runtime_review_records(knowledge)
    settings = {"max_length": 1024, "epochs": 1, "learning_rate": 0.0001, "start_from_active_release": True}
    manifest = prepare(destination, sensor_dir, generated=generated, training_configuration=settings,
                       rehearsal_limits={"style_train": 24, "advice_train": 8, "sensor_train": 4,
                                         "base_validation": 2, "sensor_validation": 2})
    manifest["training_input"] = {"source": "application_prompt_with_explicitly_simulated_snapshots",
                                  "supervision": "final_assistant_turn_only_for_new_runtime_records",
                                  "runtime_source_sha256": {name: digest(ROOT / name) for name in
                                      ("chatbot.py", "chat_knowledge.py", "chat_scope.py", "prepare_xanhnon_runtime_data.py")}}
    save_json(Path(destination) / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sensor-data", type=Path, default=Path("D:/XanhNon-auto-training/sensor-dataset"))
    args = parser.parse_args()
    manifest = prepare_runtime_data(args.output, args.sensor_data)
    print(json.dumps({key: manifest[key] for key in ("counts", "new_dialogue_counts", "deduplication", "training_configuration")}, ensure_ascii=False), flush=True)
