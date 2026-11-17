"""Exercise actual CPU NF4 adapter updates on a tiny, locally created Qwen3."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import struct
import subprocess
import sys


@unittest.skipUnless(importlib.util.find_spec('bitsandbytes'), 'Optional isolated NF4 runtime required')
class CpuNf4TrainingTests(unittest.TestCase):
    def test_real_backward_updates_adapter_and_keeps_base_frozen(self):
        import torch
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForCausalLM, BitsAndBytesConfig, Qwen3Config, Qwen3ForCausalLM
        from train_xanhnon import assistant_loss, load_cpu_nf4_model
        torch.set_num_threads(2)
        torch.manual_seed(42)
        config = Qwen3Config(vocab_size=64, hidden_size=32, intermediate_size=64,
            num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=1,
            head_dim=16, tie_word_embeddings=True)
        with tempfile.TemporaryDirectory() as temporary:
            raw, quantized = Path(temporary)/'raw', Path(temporary)/'nf4'
            Qwen3ForCausalLM(config).save_pretrained(raw)
            model = AutoModelForCausalLM.from_pretrained(raw, device_map={'':'cpu'}, dtype=torch.float32,
                quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                    bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float32))
            model.save_pretrained(quantized)
            del model
            model = load_cpu_nf4_model(quantized)
            modules=['q_proj','v_proj','o_proj','gate_proj','up_proj','down_proj']
            model = get_peft_model(model, LoraConfig(task_type='CAUSAL_LM', r=2, lora_alpha=4,
                target_modules=modules, layers_to_transform=[1], bias='none'))
            trainable = {name:param for name,param in model.named_parameters() if param.requires_grad}
            self.assertTrue(trainable)
            self.assertTrue(all('lora_' in name and '.layers.1.' in name for name in trainable))
            base_before = next(p for n,p in model.named_parameters() if 'lora_' not in n).detach().clone()
            before = {name:param.detach().clone() for name,param in trainable.items()}
            ids = torch.tensor([[2,7,11,19,4,8]])
            labels = ids.clone(); labels[:,:3] = -100
            model.train()
            optimizer = torch.optim.AdamW(trainable.values(), lr=1e-3)
            loss = assistant_loss(model, {'input_ids':ids, 'attention_mask':torch.ones_like(ids), 'labels':labels})
            loss.backward()
            self.assertTrue(torch.isfinite(loss))
            self.assertGreater(sum(float(p.grad.abs().sum()) for p in trainable.values() if p.grad is not None), 0)
            optimizer.step()
            self.assertTrue(any(not torch.equal(before[n], p) for n,p in trainable.items()))
            for module in modules:
                self.assertTrue(any('.'+module+'.' in n and not torch.equal(before[n],p)
                                    for n,p in trainable.items()),module)
            self.assertTrue(torch.equal(base_before, next(p for n,p in model.named_parameters() if 'lora_' not in n)))
            model.save_pretrained(Path(temporary)/'adapter')
            self.assertTrue((Path(temporary)/'adapter/adapter_model.safetensors').is_file())
            # The new projection set must also survive the actual deployment
            # exporter before spending hours on a full-size CPU training run.
            converter=Path(__file__).resolve().parents[1]/'.runtime/llama-converter/convert_lora_to_gguf.py'
            exported=Path(temporary)/'adapter.gguf'
            result=subprocess.run([sys.executable,str(converter),'--base',str(raw),'--outfile',str(exported),
                '--outtype','f16',str(Path(temporary)/'adapter')],capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stderr[-2500:])
            header=exported.read_bytes()[:24]
            self.assertEqual(header[:4],b'GGUF')
            self.assertEqual(struct.unpack_from('<Q',header,8)[0],len(modules)*2)


if __name__ == '__main__':
    unittest.main()
