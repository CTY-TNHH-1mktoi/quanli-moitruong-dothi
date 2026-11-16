"""Prepare a small, isolated corrective dialogue batch from reviewed failures.

Numeric monitoring contexts are explicitly hypothetical; facts/advice cite the
existing reviewed knowledge base. No evaluation question is copied into SFT.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import shutil

from prepare_xanhnon_data import make_record, stable_id, normalize
from sensor_training_data import ROOT, concise, digest, save_json


def category(aqi):
    return next(label for maximum, label in [(50, "Tốt"), (100, "Trung bình"), (150, "Kém"),
                                             (200, "Xấu"), (300, "Rất xấu"), (500, "Nguy hại")] if aqi <= maximum)


def corrective_records(knowledge):
    docs = {doc["id"]: doc for doc in knowledge["documents"]}
    questions = {
        "pm_size": ["PM10 được giới hạn ở đường kính nào?", "PM2.5 và PM10 được đặt tên theo kích thước ra sao?",
                    "Một hạt có đường kính 8 µm có thể thuộc PM10 không?", "Có phải PM10 chỉ gồm hạt to hơn 10 micromet?",
                    "Mốc 2,5 và 10 micromet dùng để phân biệt nhóm bụi như thế nào?", "Hạt PM10 có nhất thiết to hơn 10 µm không?",
                    "Đường kính tối đa thường nói tới của PM10 là gì?", "Giải thích tên hai nhóm PM10 và PM2.5 giúp mình."],
        "no_filter": ["Nhà mình chưa có thiết bị lọc, có việc gì tự làm được không?", "Mình chưa sắm máy lọc, xử lý bụi trước bằng cách gì?",
                      "Không có máy lọc sẵn ở đây, mình bắt đầu từ việc nào?", "Hiện chưa mua máy lọc được, gợi ý việc dễ làm trước nhé.",
                      "Mình muốn cách giảm bụi không cần mua thêm máy.", "Chưa có máy lọc không khí, giúp mình chọn việc làm trước.",
                      "Không sắm thêm máy được thì mình hạn chế bụi bằng cách nào?", "Tạm thời chưa có máy lọc, có thể tự vệ sinh thế nào?"],
        "noise_duration": ["Mình nên ở chỗ ồn lâu hơn để quen tai không?", "Có nên tăng thời gian ở gần máy khoan để quen tiếng?",
                           "Đứng xa nguồn ồn thì có được kéo dài thời gian nghe không?", "Muốn bớt tiếp xúc tiếng ồn, cần tăng hay giảm thời gian?",
                           "Chỗ làm ồn, mình có thể hạn chế ảnh hưởng bằng việc gì?", "Đi qua công trường ồn thì nên chú ý gì về thời gian?",
                           "Mình nên nghe tiếng lớn lâu hơn hay nghỉ ở chỗ yên?", "Giảm thời gian ở nơi ồn có phải cách bảo vệ tai không?"],
        "ask_time": ["Mình dự định đi bộ ngoài trời, nhờ bạn tư vấn nhé.", "Tư vấn giúp mình việc tập thể dục ngoài trời với.",
                     "Mình đang tính đạp xe, bạn giúp xem điều kiện môi trường nhé.", "Mình có kế hoạch vận động ở công viên, tư vấn nhé.",
                     "Nhờ bạn tư vấn hoạt động ngoài trời để mình sắp xếp.", "Tôi định đi dạo, giúp tôi chọn thời điểm theo không khí.",
                     "Mình muốn lên lịch tập ngoài trời, bạn cần biết gì?", "Bạn hỗ trợ tư vấn buổi chạy bộ của mình nhé."],
        "clarify_time": ["Vì sao bạn hỏi giờ mình tập?", "Mình chưa hiểu vì sao cần chốt giờ.", "Bạn nói rõ câu hỏi về thời điểm giúp mình.",
                         "Tại sao cần biết mình định tập hôm nào?", "Mình chưa hiểu chỗ giờ tập liên quan gì.", "Hỏi thời gian là để làm gì vậy?",
                         "Chỗ thời điểm hoạt động nghĩa là gì?", "Bạn giải thích lý do cần biết lúc tập đi."],
        "lung_followup": ["Hạt vừa nói có thể theo hơi thở vào phổi chứ?", "Vậy chúng có lọt sâu trong phổi không?",
                          "Còn khả năng đi vào phổi của loại bụi đó thì sao?", "Với kích thước ấy, bụi có vào phổi khi mình hít thở không?",
                          "Nhỏ như vậy thì có thể hít vào phổi phải không?", "Mình hít thở thì loại hạt ấy có thể xuống phổi không?",
                          "Hạt PM2.5 có thể tới phần sâu trong phổi chứ?", "Nối ý vừa rồi: loại bụi đó đi vào phổi được à?"],
    }
    result = []

    def add(topic, index, messages, source_ids):
        result.append(("train" if index < 6 else "validation", make_record(
            messages, "environment_dialogue_review", topic + ":" + str(index), topic=topic,
            source_ids=source_ids, synthetic_context=True,
            review="source_checked_facts_and_project_dialogue_policy")))

    for index in range(8):
        add("pm_size", index, [
            {"role": "user", "content": questions["pm_size"][index]},
            {"role": "assistant", "content": "PM2.5 gồm các hạt có đường kính thường không quá 2,5 µm; PM10 gồm các hạt thường không quá 10 µm. Tên nhóm dùng giới hạn kích thước, không phải nồng độ bụi."}], ["epa_pm"])
        aqi = [156, 165, 182, 191, 153, 198, 162, 186][index]
        add("aqi_category", index, [
            {"role": "user", "content": f"Tình huống giả định: US AQI {aqi}. Mức này gọi là gì và nên điều chỉnh vận động thế nào?"},
            {"role": "assistant", "content": f"US AQI {aqi} thuộc mức Xấu. Nên giảm hoạt động ngoài trời kéo dài hoặc gắng sức; nhóm nhạy cảm nên tránh các hoạt động đó ngoài trời."}], ["airnow_aqi", "airnow_particles"])
        old, fresh = 17 + index * 13, [45, 68, 118, 163, 182, 215, 37, 193][index]
        add("fresh_over_history", index, [
            {"role": "user", "content": f"Giả sử địa điểm khác có AQI {old}, thuộc mức nào?"},
            {"role": "assistant", "content": f"Với giả định đó, AQI {old} thuộc mức {category(old)}."},
            {"role": "user", "content": f"Dữ liệu bảng giám sát do ứng dụng cung cấp (giả lập mới, đúng địa điểm Hà Nội): US_AQI {fresh}. Còn chất lượng không khí Hà Nội bây giờ thuộc mức nào?"},
            {"role": "assistant", "content": f"Theo dữ liệu mới được cung cấp, Hà Nội có US AQI {fresh}, mức {category(fresh)}."}], ["project", "airnow_aqi"])
        room = ["phòng ngủ", "phòng khách", "phòng học", "phòng làm việc", "căn hộ", "nhà cạnh đường", "phòng đọc", "nhà cấp bốn"][index]
        history = [{"role": "user", "content": f"Mình muốn giảm bụi cho {room}, bạn gợi ý nhé."},
                   {"role": "assistant", "content": "Bạn có thể hạn chế nguồn bụi và dùng máy lọc phù hợp nếu có."}]
        if index % 2:
            thanks = ["Cảm ơn, mình hiểu cách làm rồi nhé.", "Mình nắm được rồi, cảm ơn bạn nhiều.",
                      "Cảm ơn bạn đã giải thích cách giảm bụi nhé.", "Mình hiểu hướng xử lý rồi, cảm ơn nhé."][index // 2]
            history.extend([{"role": "user", "content": thanks}, {"role": "assistant", "content": "Không có gì nhé!"}])
        add("no_filter", index, history + [
            {"role": "user", "content": questions["no_filter"][index]},
            {"role": "assistant", "content": "Bạn có thể hạn chế mở cửa phía đường lúc nhiều bụi và lau bằng khăn ẩm. Nếu đã có máy hút bụi, ưu tiên loại có lọc HEPA để hạn chế bụi bay lại."}], docs["indoor_dust_actions"]["source_ids"])
        add("noise_duration", index, [
            {"role": "user", "content": questions["noise_duration"][index]},
            {"role": "assistant", "content": "Hãy giảm thời gian tiếp xúc với tiếng ồn và đứng xa nguồn ồn. Nghỉ ở chỗ yên tĩnh; nếu phải ở nơi ồn, dùng nút tai hoặc chụp tai phù hợp."}], docs["noise_actions"]["source_ids"])
        pm = [23, 46, 67, 91, 12, 108, 54, 79][index]
        add("pm_not_aqi", index, [
            {"role": "user", "content": f"Giả sử cảm biến báo PM2.5 {pm} µg/m³. Dùng nguyên số đó làm chỉ số AQI được chứ?"},
            {"role": "assistant", "content": f"Không. {pm} µg/m³ là nồng độ PM2.5; AQI là chỉ số quy đổi theo cách tính và khoảng thời gian phù hợp. Không lấy nồng độ đó làm AQI trực tiếp."}], ["epa_pm", "airnow_aqi"])
        add("ask_time", index, [
            {"role": "user", "content": questions["ask_time"][index]},
            {"role": "assistant", "content": "Bạn định vận động hôm nay hay vào thời điểm khác?"}], ["project"])
        add("clarify_time", index, [
            {"role": "user", "content": questions["ask_time"][index]},
            {"role": "assistant", "content": "Bạn định vận động hôm nay hay vào thời điểm khác?"},
            {"role": "user", "content": questions["clarify_time"][index]},
            {"role": "assistant", "content": "Mình hỏi để chọn số đo hoặc dự báo đúng thời điểm bạn định vận động. Bạn định đi lúc nào?"}], ["project"])
        add("lung_followup", index, [
            {"role": "user", "content": f"Giải thích PM2.5 cho người đọc ở {room} nhé."},
            {"role": "assistant", "content": "PM2.5 là những hạt bụi có đường kính thường không quá 2,5 micromet."},
            {"role": "user", "content": questions["lung_followup"][index]},
            {"role": "assistant", "content": "Có thể. PM2.5 rất nhỏ nên có thể được hít vào sâu trong phổi."}], ["epa_pm"])
    return result


def prepare(destination, sensor_dir, generated=None, training_configuration=None, rehearsal_limits=None):
    destination, sensor_dir = Path(destination), Path(sensor_dir)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Choose an empty output directory to preserve prior data")
    base_dir = ROOT / "data/xanhnon"
    knowledge = json.loads((base_dir / "knowledge.json").read_text(encoding="utf-8"))
    generated = corrective_records(knowledge) if generated is None else generated
    limits = {"style_train": 48, "advice_train": 16, "sensor_train": 8,
              "sensor_validation": 4, "base_validation": 4, **(rehearsal_limits or {})}
    partitions = {"train": [], "validation": []}
    for split, row in generated:
        partitions[split].append(row)
    for source, count in (("environment_style", limits["style_train"]), ("environment_advice", limits["advice_train"])):
        records = [json.loads(line) for line in (base_dir / "train.jsonl").read_text(encoding="utf-8").splitlines()]
        partitions["train"].extend(sorted((r for r in records if r["source"] == source), key=lambda r:r["id"])[:count])
    for split, count in (("train", limits["sensor_train"]), ("validation", limits["sensor_validation"])):
        records = [json.loads(line) for line in (sensor_dir / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()]
        for source in sorted({r["source"] for r in records if r["source"].startswith("sensor_")}):
            partitions[split].extend(sorted((r for r in records if r["source"] == source), key=lambda r:r["id"])[:count])
    records = [json.loads(line) for line in (base_dir / "validation.jsonl").read_text(encoding="utf-8").splitlines()]
    for source in sorted({r["source"] for r in records}):
        partitions["validation"].extend(sorted((r for r in records if r["source"] == source), key=lambda r:r["id"])[:limits["base_validation"]])
    # Keep exact repeated training records once; reject cross-split record/pair leakage.
    original_total = sum(len(rows) for rows in partitions.values())
    owners, pair_owners, skipped_validation_rehearsal = {}, {}, 0
    for split, rows in partitions.items():
        unique = []
        for row in rows:
            if row["id"] in owners:
                if owners[row["id"]] != split:
                    raise ValueError("A record leaked across data splits")
                continue
            pair_keys = []
            for offset in range(1, len(row["messages"]), 2):
                key = stable_id(normalize(json.dumps(row["messages"][offset:offset+2], ensure_ascii=False, sort_keys=True)))
                pair_keys.append(key)
            if any(key in pair_owners and pair_owners[key] != split for key in pair_keys):
                if split == "validation" and row["source"].startswith("sensor_"):
                    skipped_validation_rehearsal += 1
                    continue
                raise ValueError("A repeated dialogue pair leaked across data splits")
            owners[row["id"]] = split
            for key in pair_keys:
                pair_owners[key] = split
            unique.append(row)
        partitions[split] = unique
    if {r["group_id"] for r in partitions["train"]} & {r["group_id"] for r in partitions["validation"]}:
        raise ValueError("A source group leaked across splits")
    destination.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for split, rows in partitions.items():
        random.Random(42).shuffle(rows)
        path = destination / f"{split}.jsonl"
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        artifacts[path.name] = digest(path)
    manifest = {"schema_version": 1, "built_at": datetime.now(timezone.utc).isoformat(), "seed": 42,
                "require_complete_dialogues": True,
                "required_train_sources": sorted({r["source"] for _, r in generated}),
                "required_train_topics": sorted({r["topic"] for _,r in generated}),
                "counts": {split:dict(Counter(r["source"] for r in rows)) for split,rows in partitions.items()},
                "new_dialogue_counts": {split:sum(s==split for s,_ in generated) for split in partitions},
                "total_rows": sum(len(rows) for rows in partitions.values()), "artifacts_sha256": artifacts,
                "environment_sources": knowledge["sources"], "knowledge_sha256": digest(base_dir / "knowledge.json"),
                "sources": [{"id":source,"review":"source_checked_facts_and_project_dialogue_policy"}
                            for source in sorted({r["source"] for _, r in generated})],
                "rehearsal_sources": json.loads((sensor_dir / "manifest.json").read_text(encoding="utf-8")).get("sources", []),
                "base_manifest_sha256": digest(base_dir / "manifest.json"),
                "sensor_manifest_sha256": digest(sensor_dir / "manifest.json"),
                "deduplication": {"duplicate_record_ids_removed": original_total - sum(len(rows) for rows in partitions.values()) - skipped_validation_rehearsal,
                                  "validation_rehearsal_with_shared_pairs_removed": skipped_validation_rehearsal},
                "skipped_sources": [],
                "limitations": ["Synthetic monitoring contexts are explicit assumptions, not current measurements.",
                                "Held-out dialogue phrasings share concepts; this is not independent expert certification.",
                                "A separate answer comparison is required before activation."]}
    if training_configuration:
        manifest["training_configuration"] = training_configuration
    save_json(destination / "manifest.json", manifest)
    (destination / "NOTICE.md").write_text((sensor_dir / "NOTICE.md").read_text(encoding="utf-8") + "\n\nCorrective Vietnamese dialogue written by the project using the reviewed official sources in manifest.json. Prior sensor samples are rehearsed.\n",encoding="utf-8")
    shutil.copyfile(base_dir / "LICENSE-APACHE-2.0.txt", destination / "LICENSE-APACHE-2.0.txt")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sensor-data", type=Path, default=Path("D:/XanhNon-auto-training/sensor-dataset"))
    args = parser.parse_args()
    print(json.dumps(prepare(args.output,args.sensor_data),ensure_ascii=False),flush=True)
