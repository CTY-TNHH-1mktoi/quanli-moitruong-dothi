import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import app as backend
import chatbot


class TrainingAvailabilityTests(unittest.TestCase):
    def test_model_is_not_started_during_training_and_status_is_explicit(self):
        with patch.object(chatbot, "training_in_progress", return_value=True), \
                patch.object(chatbot, "_training_chat_allowed", return_value=False), \
                patch.object(chatbot, "_create_runtime", side_effect=AssertionError("No second model")):
            self.assertEqual(chatbot.runtime_status(), {"state": "training"})
            with self.assertRaises(chatbot.ChatbotBusy):
                chatbot._load_runtime()
            # Basic source-backed questions can still answer without inference.
            reply = chatbot.generate_reply("AQI là gì?", [])["reply"]
            self.assertIn("chỉ số", reply)

    def test_verified_explanations_stay_available_in_json_and_stream(self):
        client = backend.app.test_client()
        with patch.object(chatbot, "training_in_progress", return_value=True), \
                patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Use reviewed knowledge")):
            response = client.post("/api/chat", json={"message": "Giải thích chi tiết AQI"})
            self.assertEqual(response.status_code, 200)
            self.assertIn("151–200", response.get_json()["reply"])
            response = client.post("/api/chat", json={"message": "Giải thích chi tiết AQI", "stream": True}, buffered=True)
            events = [json.loads(line[6:]) for line in response.get_data(as_text=True).splitlines() if line.startswith("data: ")]
            self.assertEqual(events[-1]["type"], "done")
            self.assertIn("AQI là chỉ số", events[-1]["reply"])

    def test_stable_native_runtime_is_allowed_with_memory_and_guarded_without_it(self):
        runtime = chatbot.NativeChatbot.__new__(chatbot.NativeChatbot)
        import psutil
        available = SimpleNamespace(available=4 * 2**30)
        with patch.dict('os.environ', {'CHATBOT_BACKEND':'auto', 'CHATBOT_CHAT_DURING_TRAINING':'1'}), \
                patch.object(chatbot, 'training_in_progress', return_value=True), \
                patch.object(chatbot, '_runtime', runtime), \
                patch.object(chatbot, '_runtime_state', 'ready'), \
                patch.object(chatbot, 'NATIVE_BINARY', SimpleNamespace(is_file=lambda: True)), \
                patch.object(chatbot, 'GGUF_PATH', SimpleNamespace(is_file=lambda: True)), \
                patch.object(psutil, 'virtual_memory', return_value=available), \
                patch.object(chatbot, '_create_runtime', side_effect=AssertionError('Reuse the stable model')):
            self.assertIs(chatbot._load_runtime(), runtime)
            self.assertEqual(chatbot.runtime_status(), {'state':'ready', 'background_training':True})
            available.available = 1 * 2**30
            with self.assertRaises(chatbot.ChatbotBusy):
                chatbot._load_runtime()
            self.assertEqual(chatbot.runtime_status(), {'state':'training'})

    def test_cold_native_runtime_requires_more_ram_and_transformers_stay_blocked(self):
        import psutil
        available = SimpleNamespace(available=2.5 * 2**30)
        with patch.dict('os.environ', {'CHATBOT_BACKEND':'auto', 'CHATBOT_CHAT_DURING_TRAINING':'1'}), \
                patch.object(chatbot, '_runtime', None), \
                patch.object(chatbot, 'NATIVE_BINARY', SimpleNamespace(is_file=lambda: True)), \
                patch.object(chatbot, 'GGUF_PATH', SimpleNamespace(is_file=lambda: True)), \
                patch.object(psutil, 'virtual_memory', return_value=available):
            self.assertFalse(chatbot._training_chat_allowed())
            available.available = 4 * 2**30
            self.assertTrue(chatbot._training_chat_allowed())
            with patch.dict('os.environ', {'CHATBOT_BACKEND':'transformers'}):
                self.assertFalse(chatbot._training_chat_allowed())


if __name__ == "__main__":
    unittest.main()
