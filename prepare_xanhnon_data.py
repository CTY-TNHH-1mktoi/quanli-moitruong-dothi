"""Build reproducible, short Vietnamese SFT data and a source-backed knowledge base.

Raw upstream files are cached under .runtime, never loaded as live AQI knowledge.
The filters are heuristics, not a claim that upstream answers were fact-checked.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import unicodedata

import requests


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "xanhnon"
CACHE_DIR = ROOT / ".runtime" / "xanhnon-data" / "raw"
SYSTEM = (
    "Bạn là Xanh Non, trợ lý môi trường. Trả lời tự nhiên bằng tiếng Việt, "
    "ngắn gọn, đúng trọng tâm, thường 2–3 câu. Chỉ dùng số liệu hiện tại khi được "
    "cung cấp đúng địa điểm và thời gian; thiếu dữ liệu thì nói rõ chưa đủ dữ liệu. "
    "Câu hỏi giả định được trả lời theo giả định, không coi là số đo hiện tại."
)
UPSTREAM = [
    {
        "id": "vietnamese_chatting",
        "repo": "MrCookieDev/Vietnamese-Chatting-Dataset",
        "revision": "9491ec151089c13a80a1bf901090c2365b1e4bda",
        "file": "hypermamba_data.jsonl", "limit": 250,
        "license": "Apache-2.0",
    },
    {
        "id": "vietnamese_multiturn",
        "repo": "5CD-AI/Vietnamese-Multi-turn-Chat-Alpaca",
        "revision": "3a1bef5b6681fe78eeaa25a97c4da1a2a1145a9e",
        "file": "vi_chatalpaca_cleaned.json", "limit": 400,
        "license": "Apache-2.0",
    },
]


def normalize(text):
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


BLOCKED = re.compile(
    r"\b(hypermamba|vimind|openai|chatgpt|gpt|claude|gemini|alexa|siri|llama|"
    r"thuoc|benh|trieu chung|bac si|chan doan|suc khoe|tap the duc|giam can|"
    r"dau tu|chung khoan|bitcoin|crypto|phap luat|luat su|tu sat|tu tu|"
    r"vu khi|chat no|ma tuy|tinh duc|virus|hack|nhac nho|dat lich|da gui|da dat|"
    r"mat khau|the tin dung|chinh tri|bau cu|tong thong|ceo|"
    r"ignore previous|bo qua (moi|tat ca) (huong dan|chi dan)|system prompt|"
    r"luu y:|kinh thua|kinh chuc|nguoi mau ngon ngu|chuoi suy nghi|"
    r"nato|phien am|truy van|sql|python|javascript|html|css|php|"
    r"thomas edison tung noi|hien tai la|gia hien tai)\b"
)
PROMISE = re.compile(r"\b(toi|minh) se (gui|nhac|goi|dat|luu|dat lich|thong bao)\b")
VAGUE_START = re.compile(r"^(vay|no |dieu do|cai do|cho vi du|vi du nua|con gi|tiep tuc|cam on)")
ENVIRONMENT = re.compile(r"\b(moi truong|tai che|rac thai|song xanh|tiet kiem (dien|nuoc)|o nhiem|nang luong|cay xanh|khi hau)\b")


def stable_id(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fetch(url, path, offline=False):
    if path.is_file():
        return
    if offline:
        raise FileNotFoundError(f"Cache missing: {path}")
    response = requests.get(url, timeout=(15, 180))
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".download")
    temporary.write_bytes(response.content)
    temporary.replace(path)


def filtered_messages(row, source_id):
    messages = row.get("messages")
    if messages is None:
        messages = [{"role": {"human": "user", "gpt": "assistant"}.get(m.get("from")),
                     "content": m.get("value")} for m in row.get("conversations", [])]
    if not messages or len(messages) % 2:
        return None, "invalid_roles"
    for i, message in enumerate(messages):
        if (message.get("role") != ("user" if i % 2 == 0 else "assistant")
                or not isinstance(message.get("content"), str)):
            return None, "invalid_roles"
    # Filter the whole source dialogue before selecting a complete short prefix.
    if BLOCKED.search(normalize(" ".join(m["content"] for m in messages))):
        return None, "identity_sensitive_or_instruction"
    kept = []
    for index in range(0, min(len(messages), 6), 2):
        pair = []
        for message in messages[index:index + 2]:
            content = message["content"].strip().replace("**", "")
            content = re.sub(r"^(Chắc chắn rồi[.!,:]?|Tất nhiên rồi[.!,:]?)\s*", "", content)
            if (not content or len(content.split()) > 80 or len(content) > 650
                    or "http" in content or "```" in content or "<|" in content
                    or PROMISE.search(normalize(content))):
                break
            pair.append({"role": message["role"], "content": content})
        if len(pair) != 2 or sum(len(m["content"]) for m in kept + pair) > 1800:
            break
        kept.extend(pair)
    minimum = 4 if source_id == "vietnamese_multiturn" else 2
    if len(kept) < minimum:
        return None, "too_long_or_no_complete_multiturn"
    if VAGUE_START.search(normalize(kept[0]["content"])):
        return None, "missing_initial_context"
    if not any(c in "ăâđêôơưáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ" for c in " ".join(m["content"].lower() for m in kept)):
        return None, "not_vietnamese"
    # Reject obvious formal/incomplete outputs without chopping a longer answer.
    if any(m["role"] == "assistant" and (m["content"].endswith((":", "...", "…"))
           or len(m["content"].splitlines()) > 5) for m in kept):
        return None, "incomplete_or_long_list"
    return kept, None


def make_record(messages, source, group_id, **metadata):
    return {"id": stable_id(source + ":" + group_id + ":" + json.dumps(messages, ensure_ascii=False))[:20],
            "group_id": source + ":" + group_id, "source": source,
            "messages": [{"role": "system", "content": SYSTEM}] + messages, **metadata}


def environment_records(knowledge):
    result = []
    for doc in knowledge["documents"]:
        for question in doc["questions"]:
            result.append(make_record([
                {"role": "user", "content": question},
                {"role": "assistant", "content": doc["answer"]},
            ], "environment_advice" if doc.get("kind") == "practical_advice" else "environment_qa", doc["id"], source_ids=doc["source_ids"],
                review="source_checked_project_examples"))
    levels = [
        (0, 50, "Tốt", "Xét riêng chất lượng không khí, bạn có thể hoạt động ngoài trời bình thường."),
        (51, 100, "Trung bình", "Bạn có thể ra ngoài; người đặc biệt nhạy cảm nên giảm thời gian và cường độ hoạt động."),
        (101, 150, "Kém", "Nhóm nhạy cảm nên giảm thời gian và cường độ hoạt động ngoài trời, nghỉ thường xuyên hơn."),
        (151, 200, "Xấu", "Mọi người nên giảm hoạt động ngoài trời kéo dài hoặc gắng sức; nhóm nhạy cảm nên tránh các hoạt động đó ngoài trời."),
        (201, 300, "Rất xấu", "Tránh hoạt động ngoài trời kéo dài hoặc gắng sức; nhóm nhạy cảm nên tránh mọi hoạt động thể chất ngoài trời."),
        (301, 500, "Nguy hại", "Mọi người nên tránh hoạt động thể chất ngoài trời; nhóm nhạy cảm nên ở trong nhà và giảm vận động."),
    ]
    for low, high, category, advice in levels:
        # Hold out a whole category rather than leaking near-duplicate numbers.
        for value in sorted({low, high, (low + high) // 2}):
            for wording in [f"Giả sử US AQI bằng {value}, tôi có nên ra ngoài không?",
                            f"Nếu US AQI là {value} thì thuộc mức nào?"]:
                result.append(make_record([
                    {"role": "user", "content": wording},
                    {"role": "assistant", "content": f"Với giả định US AQI {value}, chất lượng không khí thuộc mức {category}. {advice}"},
                ], "environment_qa", f"aqi_scenario_{low}_{high}",
                    source_ids=["airnow_particles"], review="source_checked_project_examples"))
    result.extend([
        make_record([
            {"role": "user", "content": "AQI là gì?"},
            {"role": "assistant", "content": "AQI là chỉ số chất lượng không khí. Chỉ số càng cao thì mức lo ngại đối với sức khỏe càng lớn."},
            {"role": "user", "content": "Thế nó có phải nồng độ bụi không?"},
            {"role": "assistant", "content": "Không. AQI là chỉ số quy đổi; nồng độ bụi như PM2.5 thường được đo bằng µg/m³. Không thể coi hai con số là một."},
        ], "environment_qa", "aqi_followup", source_ids=["airnow_aqi", "epa_pm"], review="source_checked_project_examples"),
        make_record([
            {"role": "user", "content": "Không có AQI thì tôi có nên ra ngoài không?"},
            {"role": "assistant", "content": "Mình chưa đủ dữ liệu để đánh giá chất lượng không khí. Bạn hãy cập nhật bảng giám sát trước."},
            {"role": "user", "content": "Cứ đoán là tốt đi."},
            {"role": "assistant", "content": "Mình chưa thể kết luận không khí tốt khi thiếu AQI. Giá trị bị thiếu không có nghĩa là bằng 0."},
        ], "environment_qa", "missing_followup", source_ids=["project"], review="source_checked_project_examples"),
    ])
    return result


def assign_split_groups(records):
    """Keep original conversations, FAQ aliases and repeated Q/A pairs together."""
    parents = list(range(len(records)))

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    owners = {}
    for index, record in enumerate(records):
        keys = ["source-group:" + record["group_id"]]
        messages = record["messages"][1:]
        for position in range(0, len(messages), 2):
            question, answer = messages[position:position + 2]
            keys.append("pair:" + stable_id(normalize(question["content"]) + "\n" + normalize(answer["content"])))
        for key in keys:
            if key in owners:
                parents[root(index)] = root(owners[key])
            owners[key] = index
    families = {}
    for index, record in enumerate(records):
        families.setdefault(root(index), []).append(record["id"])
    for index, record in enumerate(records):
        record["source_group"] = record["group_id"]
        record["group_id"] = "family:" + min(families[root(index)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--preserve-split", action="store_true", help="Keep existing records in their original split")
    args = parser.parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    knowledge = json.loads((DATA_DIR / "knowledge.json").read_text(encoding="utf-8"))
    records, source_reports, seen = [], [], set()
    for source in UPSTREAM:
        base_url = f"https://huggingface.co/datasets/{source['repo']}/resolve/{source['revision']}/"
        raw_path = CACHE_DIR / source["file"]
        fetch(base_url + source["file"], raw_path, args.offline)
        fetch(base_url + "README.md", CACHE_DIR / (source["id"] + "_README.md"), args.offline)
        text = raw_path.read_text(encoding="utf-8-sig")
        rows = [json.loads(line) for line in text.splitlines() if line.strip()] if raw_path.suffix == ".jsonl" else json.loads(text)
        rejected, candidates = Counter(), []
        for index, row in enumerate(rows):
            messages, reason = filtered_messages(row, source["id"])
            if reason:
                rejected[reason] += 1
                continue
            key = stable_id(normalize(json.dumps(messages, ensure_ascii=False)))
            if key in seen:
                rejected["duplicate"] += 1
                continue
            seen.add(key)
            record = make_record(messages, source["id"], str(row.get("id", index)),
                                 review="automatic_rules_only", license=source["license"])
            candidates.append(record)
        random.Random(42).shuffle(candidates)
        candidates.sort(key=lambda r: not bool(ENVIRONMENT.search(normalize(" ".join(m["content"] for m in r["messages"][1:])))))
        selected = candidates[:source["limit"]]
        records.extend(selected)
        source_reports.append({**source, "url": "https://huggingface.co/datasets/" + source["repo"],
                               "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                               "raw_rows": len(rows), "eligible_rows": len(candidates),
                               "selected_rows": len(selected), "rejected": dict(rejected)})
        print(f"{source['id']}: {len(rows)} raw -> {len(candidates)} eligible -> {len(selected)} selected", flush=True)
    records.extend(environment_records(knowledge))
    from xanhnon_style_data import style_records
    records.extend(style_records(make_record))
    assign_split_groups(records)
    # Split complete source groups. Aliases, same-document answers and numeric
    # variants cannot appear in both train and validation.
    partitions = {"train": [], "validation": []}
    previous_split = {}
    if args.preserve_split:
        for split in partitions:
            path = DATA_DIR / f"{split}.jsonl"
            if path.is_file():
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        old = json.loads(line)
                        previous_split[old["id"]] = split
    groups = {}
    for record in records:
        groups.setdefault(record["group_id"], []).append(record)
    buckets = {}
    for group_id, group in groups.items():
        sources = {record["source"] for record in group}
        category = "environment_qa" if "environment_qa" in sources else sorted(sources)[0]
        buckets.setdefault(category, []).append(group_id)
    validation_groups = set()
    for category, group_ids in buckets.items():
        group_ids.sort(key=stable_id)
        count = max(1, round(len(group_ids) * 0.1)) if len(group_ids) > 1 else 0
        validation_groups.update(group_ids[:count])
    for record in records:
        old_splits = {previous_split[item["id"]] for item in groups[record["group_id"]] if item["id"] in previous_split}
        if len(old_splits) > 1:
            raise ValueError("New examples merge old train/validation families; review duplicates before preparing")
        split = next(iter(old_splits)) if old_splits else ("validation" if record["group_id"] in validation_groups else "train")
        partitions[split].append(record)
    artifacts = {}
    for split, rows in partitions.items():
        random.Random(42).shuffle(rows)
        content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        target = DATA_DIR / f"{split}.jsonl"
        temporary = target.with_suffix(".jsonl.new")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)
        artifacts[target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1, "built_at": datetime.now(timezone.utc).isoformat(),
        "seed": 42, "sources": source_reports,
        "environment_sources": knowledge["sources"],
        "knowledge_documents": len(knowledge["documents"]),
        "counts": {split: dict(Counter(row["source"] for row in rows)) for split, rows in partitions.items()},
        "total_rows": len(records),
        "artifacts_sha256": artifacts,
        "limitations": ["Upstream samples are filtered automatically, not individually verified.",
                        "General dialogue examples are training data, not authoritative environmental knowledge.",
                        "Preparing this dataset does not update model weights.",
                        "No real-time sensor reading is stored as a current fact in the dataset."],
    }
    (DATA_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fetch("https://www.apache.org/licenses/LICENSE-2.0.txt", DATA_DIR / "LICENSE-APACHE-2.0.txt", args.offline)
    print(json.dumps({"total": len(records), "splits": manifest["counts"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
