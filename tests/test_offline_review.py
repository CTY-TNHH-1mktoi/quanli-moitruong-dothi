import unittest
import tempfile
from pathlib import Path

from review_xanhnon_offline import parse_completion, tokenizer_files
from sensor_training_data import digest


class OfflineReviewTests(unittest.TestCase):
    def test_split_tokenizer_is_supported_and_vocab_changes_are_detectable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('tokenizer_config.json', 'vocab.json', 'merges.txt', 'added_tokens.json'):
                (root / name).write_text('{}', encoding='utf-8')
            before = {path.name: digest(path) for path in tokenizer_files(root)}
            self.assertNotIn('tokenizer.json', before)
            (root / 'vocab.json').write_text('{"changed": 1}', encoding='utf-8')
            after = {path.name: digest(path) for path in tokenizer_files(root)}
            self.assertNotEqual(before['vocab.json'], after['vocab.json'])
            self.assertIn('added_tokens.json', before)
            (root / 'merges.txt').unlink()
            with self.assertRaises(FileNotFoundError):
                tokenizer_files(root)

    def test_fast_tokenizer_does_not_require_split_vocab_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('tokenizer_config.json', 'tokenizer.json'):
                (root / name).write_text('{}', encoding='utf-8')
            self.assertEqual(len(tokenizer_files(root)), 2)

    def test_only_terminal_decoration_is_removed(self):
        raw = '\nAQI is an index. [end of text] is quoted.<|im_end|> [end of text]\n\n'
        self.assertEqual(parse_completion(raw), {
            'reply': 'AQI is an index. [end of text] is quoted.', 'truncated': False})

    def test_missing_or_nonterminal_end_token_stays_truncated(self):
        self.assertTrue(parse_completion('An unfinished answer')['truncated'])
        self.assertTrue(parse_completion('A <|im_end|> B')['truncated'])

    def test_empty_generation_does_not_pass_as_an_answer(self):
        with self.assertRaises(ValueError):
            parse_completion('<|im_end|> [end of text]\n')


if __name__ == '__main__':
    unittest.main()
