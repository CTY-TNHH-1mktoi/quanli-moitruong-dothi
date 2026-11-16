import unittest

from prepare_xanhnon_dialogue_sources import filter_dialogue, pair_keys
from prepare_xanhnon_data import normalize


class DialogueSourceTests(unittest.TestCase):
    def test_multiturn_keeps_the_context_and_complete_answers(self):
        messages = [
            {'role': 'user', 'content': 'Giúp mình sửa câu này cho dễ hiểu: mình đang đi tới nhà.'},
            {'role': 'assistant', 'content': 'Bạn có thể viết: “Mình đang về nhà.”'},
            {'role': 'user', 'content': 'Thế nếu muốn nói trang trọng hơn thì sao?'},
            {'role': 'assistant', 'content': 'Bạn có thể đổi thành: “Tôi đang trở về nhà.”'},
        ]
        kept, reason = filter_dialogue(messages, multi=True, heldout=set())
        self.assertIsNone(reason)
        self.assertEqual(kept, messages)

    def test_heldout_followup_is_blocked_even_with_a_different_initial_question(self):
        messages = [
            {'role': 'user', 'content': 'Chào bạn, mình muốn hỏi một chút.'},
            {'role': 'assistant', 'content': 'Bạn cứ hỏi nhé.'},
            {'role': 'user', 'content': 'Thế ngày mai thì sao?'},
            {'role': 'assistant', 'content': 'Bạn muốn hỏi về chủ đề nào cho ngày mai?'},
        ]
        kept, reason = filter_dialogue(messages, multi=True, heldout={normalize('Thế ngày mai thì sao?')})
        self.assertIsNone(kept)
        self.assertEqual(reason, 'heldout_question')

    def test_private_data_in_an_unused_suffix_is_still_rejected(self):
        messages = [
            {'role': 'user', 'content': 'Chào bạn nhé.'},
            {'role': 'assistant', 'content': 'Chào bạn, mình có thể giúp gì?'},
        ] * 3 + [
            {'role': 'user', 'content': 'Gửi kết quả đến example@example.com nhé.'},
            {'role': 'assistant', 'content': 'Mình không gửi thư được.'},
        ]
        self.assertEqual(filter_dialogue(messages, multi=True, heldout=set())[1], 'sensitive_or_injection')

    def test_unverified_environment_answers_are_not_knowledge(self):
        messages = [
            {'role': 'user', 'content': 'Không khí và khí hậu khác nhau thế nào?'},
            {'role': 'assistant', 'content': 'Đó là hai khái niệm khác nhau trong đời sống.'},
        ]
        self.assertEqual(filter_dialogue(messages, multi=False, heldout=set())[1],
                         'environment_answer_needs_source_review')

    def test_fictional_assistant_memories_are_not_selected(self):
        messages = [
            {'role': 'user', 'content': 'Bạn có nhớ buổi dạo chơi ấy không?'},
            {'role': 'assistant', 'content': 'Tôi nhớ lần đi dạo ở hồ với bạn.'},
        ]
        self.assertEqual(filter_dialogue(messages, multi=False, heldout=set())[1],
                         'invented_assistant_experience')

    def test_multiturn_does_not_fall_back_to_a_single_pair(self):
        messages = [{'role': 'user', 'content': 'Chào bạn nhé.'},
                    {'role': 'assistant', 'content': 'Chào bạn, mình có thể giúp gì?'}]
        self.assertIsNone(filter_dialogue(messages, multi=True, heldout=set())[0])

    def test_duplicate_pairs_are_normalized(self):
        a = [{'role': 'user', 'content': 'Chào bạn nhé!'},
             {'role': 'assistant', 'content': 'Chào bạn.'}]
        b = [{'role': 'user', 'content': 'CHÀO BẠN NHÉ!'},
             {'role': 'assistant', 'content': 'Chào  bạn.'}]
        self.assertEqual(pair_keys(a), pair_keys(b))

    def test_vietnamese_prompt_does_not_admit_an_english_assistant(self):
        messages = [
            {'role': 'user', 'content': 'Bạn gợi ý cho mình một cách học dễ nhớ nhé.'},
            {'role': 'assistant', 'content': 'As an AI language model, I recommend taking short notes.'},
        ]
        self.assertEqual(filter_dialogue(messages, multi=False, heldout=set())[1],
                         'non_vietnamese_assistant_turn')


if __name__ == '__main__':
    unittest.main()
