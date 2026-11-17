import json
from pathlib import Path
import tempfile
import unittest

from evaluate_xanhnon import evaluation_cases, load_comparison, assess, compare_answers


class EvaluationComparisonTests(unittest.TestCase):
    def test_pm25_range_with_intervening_units_is_not_a_correct_definition(self):
        case = next(c for c in evaluation_cases()[0] if c['id'] == 'fine_particles')
        for number in ('2,5', '2.5'):
            reply = f'PM2.5 là hạt có đường kính từ {number} micromet đến 10 micromet, có thể vào phổi.'
            result = assess(case, {'reply': reply, 'truncated': False}, 0)
            self.assertIn('incorrect_PM25_size_range_2_5_to_10', result['violations'])
        good = assess(case, {'reply': 'PM2.5 có đường kính thường không quá 2,5 micromet, có thể vào sâu trong phổi.', 'truncated': False}, 0)
        self.assertTrue(good['passed'], good['violations'])

    def test_lung_followup_cannot_pass_by_denying_the_correct_fact(self):
        case = next(c for c in evaluation_cases()[0] if c['id'] == 'followup')
        wrong = assess(case, {'reply': 'Không, PM2.5 không thể đi sâu qua phổi.', 'truncated': False}, 0)
        self.assertIn('incorrect_denial_of_particle_lung_penetration', wrong['violations'])
        good = assess(case, {'reply': 'Có. PM2.5 có thể được hít vào sâu trong phổi.', 'truncated': False}, 0)
        self.assertTrue(good['passed'], good['violations'])

    def test_source_metadata_is_not_user_facing_prose(self):
        for label in ('source_ids', 'source_id'):
            wrong = assess({'id': 'ozone', 'question': 'Ozone?'}, {'reply': f'Theo {label} là EPA, ozone có thể kích ứng phổi.', 'truncated': False}, 0)
            self.assertIn('internal_context_label_leak', wrong['violations'])

    def test_noise_duration_words_are_not_enough_without_a_protective_action(self):
        case = {'id': 'noise', 'question': 'Nghe lâu để quen tai?', 'check_noise_duration': True}
        wrong = assess(case, {'reply': 'Không. Thính giác giảm dần theo thời gian khi tiếp xúc với tiếng ồn.', 'truncated': False}, 0)
        self.assertIn('missing_action_to_reduce_noise_exposure_duration', wrong['violations'])
        good = assess(case, {'reply': 'Không. Nên giảm thời gian nghe và đứng xa nguồn ồn.', 'truncated': False}, 0)
        self.assertTrue(good['passed'], good['violations'])

    def test_greeting_requires_acknowledgment_not_an_echo(self):
        case = {'id': 'balanced_greeting', 'question': 'Chào, bạn có ở đây không?'}
        wrong = assess(case, {'reply': 'Bạn đang ở đây chứ?', 'truncated': False}, 0)
        self.assertIn('greeting_replaced_by_echo_or_question', wrong['violations'])
        good = assess(case, {'reply': 'Chào bạn! Mình đây, bạn cứ hỏi nhé.', 'truncated': False}, 0)
        self.assertTrue(good['passed'], good['violations'])

    def test_aqi_definition_cannot_be_replaced_with_a_missing_data_notice(self):
        cases, _ = evaluation_cases()
        case = next(case for case in cases if case['id'] == 'explain_aqi')
        wrong = assess(case, {'reply': 'Mình chưa có dữ liệu AQI hiện tại. Hãy tìm thông tin chất lượng không khí ở nguồn khác.', 'truncated': False}, 0)
        self.assertIn('definition_replaced_by_missing_current_data', wrong['violations'])
        right = assess(case, {'reply': 'AQI là chỉ số thể hiện chất lượng không khí và mức lo ngại đối với sức khỏe.', 'truncated': False}, 0)
        self.assertTrue(right['passed'], right['violations'])

    def test_pm10_cannot_be_described_as_harmless_even_with_correct_size_numbers(self):
        cases, _ = evaluation_cases()
        case = next(case for case in cases if case['id'] == 'compare_particles')
        prefix = 'PM2.5 thường không quá 2,5 µm; PM10 thường không quá 10 µm. '
        for claim in ['PM10 lớn hơn, không ảnh hưởng nhiều đến sức khỏe.', 'PM10 là bụi vô hại.']:
            result = assess(case, {'reply': prefix + claim, 'truncated': False}, 0)
            self.assertIn('unsupported_claim_PM10_harmless', result['violations'])
        right = assess(case, {'reply': prefix + 'Không nên coi PM10 là vô hại.', 'truncated': False}, 0)
        self.assertTrue(right['passed'], right['violations'])

    def test_losing_the_correct_current_number_is_a_regression_even_if_both_answers_fail(self):
        before = {"city": {"passed": False, "violations": ["missing: xấu"]}}
        after = [{"id": "city", "passed": False, "violations": ["missing: xấu", "missing: 175", "unwanted: AQI 20"]}]
        compared = compare_answers(before, after, 8)
        self.assertFalse(compared["eligible_for_manual_review"])
        self.assertEqual(compared["regressions"], ["city"])
    def test_wrong_pm10_size_cannot_pass_by_merely_mentioning_both_numbers(self):
        cases, _ = evaluation_cases()
        case = next(case for case in cases if case["id"] == "compare_particles")
        wrong = assess(case, {"reply": "PM2.5 nhỏ hơn 2,5 µm; PM10 chỉ lớn hơn 10 µm.", "truncated": False}, 0)
        self.assertFalse(wrong["passed"])
        right = assess(case, {"reply": "PM2.5 thường không quá 2,5 µm; PM10 có đường kính không lớn hơn 10 µm.", "truncated": False}, 0)
        self.assertTrue(right["passed"], right["violations"])

    def test_consultation_must_actually_ask_the_question(self):
        case = {"id": "ask", "question": "Tư vấn chạy bộ", "required_any": [["?"], ["hôm nay"]]}
        self.assertFalse(assess(case, {"reply": "Hôm nay nên hạn chế vận động ngoài trời.", "truncated": False}, 0)["passed"])
        self.assertTrue(assess(case, {"reply": "Bạn định chạy hôm nay hay hôm khác?", "truncated": False}, 0)["passed"])

    def test_noise_advice_cannot_recommend_increasing_exposure(self):
        case = {"id": "noise_concrete_actions", "question": "Giảm tiếng ồn"}
        for place in ('nơi ồn', 'chỗ ồn', 'tiếng ồn'):
            with self.subTest(place=place):
                wrong = assess(case, {"reply": f"Hãy giảm âm lượng, tăng khoảng cách từ nguồn ồn và thời gian ở {place}.", "truncated": False}, 0)
                self.assertIn('unsafe_increase_noise_exposure_duration', wrong['violations'])
                right = assess(case, {"reply": f"Hãy tăng khoảng cách và giảm thời gian ở {place}.", "truncated": False}, 0)
                self.assertTrue(right["passed"], right["violations"])

    def test_no_filter_constraint_requires_an_action_without_a_new_device(self):
        case = {"id": "dust_without_filter_followup", "question": "Chưa mua được máy lọc"}
        self.assertFalse(assess(case, {"reply": "Có thể lắp máy lọc HEPA hoặc máy hút bụi có HEPA.", "truncated": False}, 0)["passed"])
        self.assertTrue(assess(case, {"reply": "Bạn có thể lau bụi bằng khăn ẩm và hạn chế mở cửa phía đường.", "truncated": False}, 0)["passed"])

    def test_consultation_cases_are_unique_and_not_exact_training_questions(self):
        root = Path(__file__).resolve().parents[1]
        cases, fingerprint = evaluation_cases(root / "data/xanhnon/eval_consultation.json")
        self.assertEqual(len(cases), 20)
        self.assertEqual(len(fingerprint), 64)
        questions = set()
        for split in ("train", "validation"):
            for line in (root / f"data/xanhnon/{split}.jsonl").read_text(encoding="utf-8").splitlines():
                questions.update(turn["content"] for turn in json.loads(line)["messages"] if turn["role"] == "user")
        for case in cases[11:]:
            self.assertNotIn(case["question"], questions)

    def test_comparison_rejects_changed_scope_or_missing_cases(self):
        cases, _ = evaluation_cases()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            path.write_text(json.dumps({"evaluation_scope": "application_pipeline", "cases": cases[:-1]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "same evaluation cases"):
                load_comparison(path, "application_pipeline", cases)
            with self.assertRaisesRegex(ValueError, "same evaluation scope"):
                load_comparison(path, "core_generation_without_deterministic_replies", cases)


if __name__ == "__main__":
    unittest.main()
