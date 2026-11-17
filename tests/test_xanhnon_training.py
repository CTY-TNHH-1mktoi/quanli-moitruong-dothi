"""Check that the cheaper assistant-only loss preserves training gradients."""

import unittest

from train_xanhnon import assistant_loss


class AssistantLossTests(unittest.TestCase):
    def test_selected_logits_match_full_masked_loss_and_gradients(self):
        import torch
        from transformers import Qwen2Config, Qwen2ForCausalLM
        torch.manual_seed(7)
        torch.set_num_threads(2)
        model = Qwen2ForCausalLM(Qwen2Config(
            vocab_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2,
            num_attention_heads=4, num_key_value_heads=2, attention_dropout=0,
        )).eval()
        ids = torch.tensor([[1, 2, 3, 4, 5, 6, 7, 8]])
        inputs = {"input_ids": ids, "attention_mask": torch.ones_like(ids),
                  "labels": torch.tensor([[-100, -100, 3, 4, -100, -100, 7, 8]])}
        full = model(**inputs).loss
        full.backward()
        gradients = {name: p.grad.clone() for name, p in model.named_parameters() if p.grad is not None}
        model.zero_grad(set_to_none=True)
        selected = assistant_loss(model, inputs)
        selected.backward()
        torch.testing.assert_close(selected, full, atol=1e-6, rtol=1e-6)
        for name, parameter in model.named_parameters():
            if name in gradients:
                torch.testing.assert_close(parameter.grad, gradients[name], atol=1e-6, rtol=1e-5)


if __name__ == "__main__":
    unittest.main()
