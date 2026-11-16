"""Keep retrieved facts grounded and live readings separate from training data."""

import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import chatbot
from chat_knowledge import exact_answer, reference_context, retrieve
from prepare_xanhnon_data import assign_split_groups, filtered_messages


ROOT = Path(__file__).resolve().parents[1]


class KnowledgeTests(unittest.TestCase):
    def test_known_faq_can_answer_without_model(self):
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("FAQ should not load model")):
            reply = chatbot.generate_reply("Bụi mịn sinh ra từ đâu?", [], None)["reply"]
        self.assertIn("công trường", reply)

    def test_current_reading_question_cannot_be_answered_from_static_knowledge(self):
        self.assertIsNone(exact_answer("AQI hiện tại ở Hà Nội là bao nhiêu?"))
        reply = chatbot.generate_reply("AQI hiện tại là bao nhiêu?", [], None)["reply"]
        self.assertIn("chưa đủ dữ liệu", reply)

    def test_general_missing_data_faq_is_not_replaced_with_current_readings(self):
        reply = chatbot.generate_reply("Chưa có dữ liệu AQI có nghĩa không khí tốt không?", [],
                                       {"DuLieu": {"US_AQI": 175}})["reply"]
        self.assertIn("chưa đủ dữ liệu", reply)
        self.assertNotIn("175", reply)

    def test_detailed_conceptual_answer_receives_references_without_live_measurements(self):
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Use verified facts directly")):
            reply = chatbot.generate_reply("Giải thích chi tiết PM2.5 ảnh hưởng sức khỏe thế nào?", [],
                                           {"DuLieu": {"US_AQI": 175, "PM25": 45.4}})["reply"]
        self.assertIn("phổi", reply)
        self.assertIn("tim mạch", reply)
        self.assertNotIn("45.4", reply)
        self.assertNotIn("175", reply)

    def test_followup_retrieval_uses_user_context_not_assistant_inventions(self):
        context = reference_context("Nó từ đâu ra?", [
            {"role": "user", "content": "PM2.5 là gì?"},
            {"role": "assistant", "content": "SECRET_FAKE_AQI_999"},
        ])
        self.assertIn("Nguồn phát sinh bụi", context)
        self.assertNotIn("SECRET_FAKE_AQI_999", context)

    def test_conversational_subject_selects_relevant_facts(self):
        cases = [
            ("PM2.5 nhỏ tới mức nào và có vào phổi được không?", "pm25_definition"),
            ("Ở trong phòng là hết lo bụi mịn rồi phải không bạn?", "indoor_particles"),
            ("Trong thành phố, bụi mịn chủ yếu từ đâu tới vậy?", "pm_sources"),
            ("Giả sử US AQI lên 175 thì nên tập ngoài trời ra sao?", "aqi_categories"),
        ]
        for question, expected in cases:
            with self.subTest(question=question):
                matches = retrieve(question)
                self.assertEqual(matches[0]["id"], expected)
                self.assertNotIn("data_source", [match["id"] for match in matches])

    def test_conversational_followup_retrieves_facts_but_new_topic_does_not_inherit_them(self):
        history = [{"role": "user", "content": "PM2.5 là gì?"},
                   {"role": "assistant", "content": "PM2.5 là bụi mịn."}]
        context = reference_context("Nó có thể đi sâu tới phổi không bạn?", history)
        self.assertIn("epa.gov", context)
        self.assertIn("đi sâu vào phổi", context)
        self.assertNotIn("PM2.5", reference_context("Cách phân loại rác?", history))

    def test_unrelated_question_has_no_environment_answer(self):
        self.assertIsNone(exact_answer("Hãy đặt báo thức lúc 7 giờ sáng"))
        self.assertEqual(retrieve("Hướng dẫn lập trình Python"), [])

    def test_every_knowledge_entry_has_resolvable_sources(self):
        knowledge = json.loads((ROOT / "data/xanhnon/knowledge.json").read_text(encoding="utf-8"))
        for document in knowledge["documents"]:
            self.assertTrue(document["source_ids"])
            self.assertTrue(set(document["source_ids"]) <= knowledge["sources"].keys())
            self.assertLessEqual(len(document["answer"].split()), 85)


class DatasetTests(unittest.TestCase):
    def test_wrong_identity_and_fake_actions_are_filtered(self):
        for content in ["Mình là HyperMamba của Vimind.", "Mình đã đặt lịch nhắc bạn lúc 8 giờ.",
                        "Tôi sẽ gửi email cho bạn."]:
            row = {"messages": [{"role": "user", "content": "Bạn giúp mình nhé?"},
                                {"role": "assistant", "content": content}]}
            self.assertIsNone(filtered_messages(row, "vietnamese_chatting")[0])

    def test_long_answers_are_rejected_without_sentence_truncation(self):
        row = {"messages": [{"role": "user", "content": "Giải thích giúp mình."},
                            {"role": "assistant", "content": "Đây là câu rất dài. " * 30}]}
        self.assertIsNone(filtered_messages(row, "vietnamese_chatting")[0])

    def test_shared_qa_pair_merges_original_groups(self):
        pair = [{"role": "system", "content": "Xanh Non"},
                {"role": "user", "content": "Bụi mịn là gì?"},
                {"role": "assistant", "content": "Đó là các hạt bụi nhỏ."}]
        records = [{"id": "a", "group_id": "one", "messages": pair},
                   {"id": "b", "group_id": "two", "messages": pair}]
        assign_split_groups(records)
        self.assertEqual(records[0]["group_id"], records[1]["group_id"])

    def test_exported_data_has_no_split_leaks_or_wrong_identity(self):
        splits = {name: [json.loads(line) for line in (ROOT / f"data/xanhnon/{name}.jsonl").read_text(encoding="utf-8").splitlines()]
                  for name in ("train", "validation")}
        self.assertFalse({r["group_id"] for r in splits["train"]} & {r["group_id"] for r in splits["validation"]})
        pairs = {}
        for split, records in splits.items():
            pairs[split] = set()
            for record in records:
                messages = record["messages"]
                self.assertEqual(messages[0]["role"], "system")
                self.assertEqual(messages[-1]["role"], "assistant")
                for index in range(1, len(messages), 2):
                    self.assertEqual(messages[index]["role"], "user")
                    self.assertEqual(messages[index + 1]["role"], "assistant")
                    self.assertLessEqual(len(messages[index + 1]["content"].split()), 85)
                    self.assertNotRegex(messages[index + 1]["content"].lower(), "hypermamba|vimind")
                    pairs[split].add((messages[index]["content"], messages[index + 1]["content"]))
        self.assertFalse(pairs["train"] & pairs["validation"])


if __name__ == "__main__":
    unittest.main()
