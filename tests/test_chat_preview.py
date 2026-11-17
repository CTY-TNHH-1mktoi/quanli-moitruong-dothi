import os
import unittest
from unittest.mock import Mock, patch

import chatbot
from chat_briefing_v15 import compact_messages
from location_catalog import get_location


class ChatPreviewTests(unittest.TestCase):
    def test_runtime_receives_gpu_configuration(self):
        with patch.dict(os.environ, {'CHATBOT_BACKEND': 'llama_cpp', 'CHATBOT_GPU_LAYERS': '99',
                                     'CHATBOT_CPU_THREADS': '2'}), \
                patch.object(chatbot, 'training_in_progress', return_value=False), \
                patch.object(chatbot, 'NativeChatbot') as factory:
            chatbot._create_runtime()
        self.assertEqual(factory.call_args.kwargs['gpu_layers'], 99)
        self.assertEqual(factory.call_args.args[2], 2)

    def test_unhandled_environment_question_receives_the_preview_evidence_profile(self):
        question = 'Vì sao gió yếu có thể khiến bụi khó phát tán?'
        snapshot = {'DiaDiem': get_location('hanoi'), 'DuLieu': {'US_AQI': 83}}
        runtime = chatbot.NativeChatbot.__new__(chatbot.NativeChatbot)
        runtime.generate = Mock(return_value={'reply': 'Mình sẽ giải thích theo thông tin hiện có.', 'truncated': False})
        from chat_briefing_v16 import compact_messages as revised_messages
        for profile,builder in [('grounded-v15',compact_messages),('grounded-v16',revised_messages)]:
            runtime.generate.reset_mock()
            with self.subTest(profile=profile), \
                    patch.object(chatbot, 'MODEL_PROMPT_PROFILE', profile), \
                    patch.object(chatbot, '_load_runtime', return_value=runtime):
                chatbot.generate_reply(question, [], snapshot)
            runtime.generate.assert_called_once()
            self.assertEqual(runtime.generate.call_args.args[0], builder(question, [], snapshot))


if __name__ == '__main__':
    unittest.main()
