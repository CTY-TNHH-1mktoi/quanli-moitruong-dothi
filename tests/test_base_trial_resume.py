import unittest

from evaluate_xanhnon_base_trial import assess_stdout, validate_resume


class BaseTrialResumeTests(unittest.TestCase):
    def test_empty_output_is_a_failed_case_without_aborting_the_next_answer(self):
        case = {'id': 'generic', 'question': 'Example'}
        empty = assess_stdout(case, '<|im_end|> [end of text]\n', 1.0)
        self.assertFalse(empty['passed'])
        self.assertIn('empty_generation', empty['violations'])
        normal = assess_stdout(case, 'A complete answer.<|im_end|> [end of text]\n', 1.0)
        self.assertTrue(normal['passed'])

    def test_resume_requires_the_same_model_inputs_and_prefix(self):
        previous = {'status': 'failed', 'error': 'Empty CLI generation',
                    'model_sha256': 'model', 'binary_sha256': 'binary', 'cases_sha256': 'cases',
                    'prompt_profile': 'grounded-v15', 'completed_cases': 1,
                    'application_sha256': {'evaluate_xanhnon.py': 'frozen'}}
        cases = [{'id': 'first'}, {'id': 'second'}]
        rows = [{'id': 'first'}]
        hashes = {'evaluate_xanhnon.py': 'frozen'}
        validate_resume(previous, cases, rows, hashes, 'model', 'binary', 'cases')
        for replacement in [({'evaluate_xanhnon.py': 'changed'}, 'model', 'binary', 'cases'),
                            (hashes, 'other-model', 'binary', 'cases'),
                            (hashes, 'model', 'binary', 'changed-cases')]:
            with self.assertRaises(ValueError):
                validate_resume(previous, cases, rows, *replacement)
        with self.assertRaises(ValueError):
            validate_resume(previous, cases, [{'id': 'second'}], hashes, 'model', 'binary', 'cases')


if __name__ == '__main__':
    unittest.main()
