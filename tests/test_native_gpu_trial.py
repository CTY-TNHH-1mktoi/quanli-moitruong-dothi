from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from native_chatbot import NativeChatbot


class NativeGPUTrialTests(unittest.TestCase):
    def test_requested_lora_is_loaded_explicitly_and_missing_adapter_does_not_spawn(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = root/'candidate adapter.gguf'
            with patch('native_chatbot.subprocess.Popen') as spawn:
                with self.assertRaises(FileNotFoundError):
                    NativeChatbot(root/'server.exe', root/'model.gguf', 2, 2048, 192, lora_path=adapter)
                spawn.assert_not_called()
            adapter.write_bytes(b'GGUF')
            process = Mock()
            process.poll.return_value = None
            with patch('native_chatbot.subprocess.Popen',return_value=process) as spawn, \
                    patch('native_chatbot.requests.get',return_value=Mock(status_code=200)), \
                    patch('native_chatbot.atexit.register'):
                runtime = NativeChatbot(root/'server.exe',root/'model.gguf',2,2048,192,
                    gpu_layers=99,log_path=root/'test.log',lora_path=adapter)
                arguments = spawn.call_args.args[0]
                self.assertEqual(arguments[arguments.index('--lora')+1],str(adapter))
                runtime.close()

    def test_cpu_default_and_explicit_gpu_use_the_requested_layer_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for options, expected in [({}, '0'), ({'gpu_layers': 99}, '99')]:
                process = Mock()
                process.poll.return_value = None
                with patch('native_chatbot.subprocess.Popen', return_value=process) as spawn, \
                        patch('native_chatbot.requests.get', return_value=Mock(status_code=200)), \
                        patch('native_chatbot.atexit.register'):
                    runtime = NativeChatbot(root/'server.exe', root/'model.gguf', 2, 8192, 192,
                                            log_path=root/'trial.log', **options)
                    arguments = spawn.call_args.args[0]
                    self.assertEqual(arguments[arguments.index('-ngl') + 1], expected)
                    self.assertEqual(arguments[arguments.index('--host') + 1], '127.0.0.1')
                    runtime.close()
                    process.terminate.assert_called_once()

    def test_invalid_gpu_configuration_does_not_launch_a_process(self):
        for value in [-1, 1.5, True, '99', 1000]:
            with patch('native_chatbot.subprocess.Popen') as spawn:
                with self.assertRaises(ValueError):
                    NativeChatbot('server.exe', 'model.gguf', 2, 8192, 192, gpu_layers=value)
                spawn.assert_not_called()


if __name__ == '__main__':
    unittest.main()
