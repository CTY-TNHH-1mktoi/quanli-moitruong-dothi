"""Measure a real saved LoRA checkpoint without claiming a completed full epoch."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

from train_xanhnon import ROOT, assistant_loss, load_data, save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base", type=Path, default=ROOT / "models/xanhnon-qwen2.5-0.5b-vietnamese")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Choose an empty review directory")
    progress = json.loads((args.checkpoint / "progress.json").read_text(encoding="utf-8"))
    current_manifest = hashlib.sha256((ROOT / "data/xanhnon/manifest.json").read_bytes()).hexdigest()
    if current_manifest != progress["manifest_sha256"]:
        parser.error("Dataset changed since this checkpoint; keep the original evaluation split")
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(4)
    tokenizer = AutoTokenizer.from_pretrained(args.base, local_files_only=True, use_fast=False)
    data, _ = load_data(tokenizer, progress["max_length"],
                        validation_limit=progress["configuration"]["validation_limit"])
    model = AutoModelForCausalLM.from_pretrained(args.base, local_files_only=True, trust_remote_code=False,
                                                use_safetensors=True, dtype=torch.float32,
                                                attn_implementation="sdpa", low_cpu_mem_usage=True)
    model = PeftModel.from_pretrained(model, args.checkpoint, is_trainable=False, local_files_only=True).eval()
    started = time.monotonic()
    numerator, denominator = 0.0, 0
    with torch.no_grad():
        for index, item in enumerate(data["validation"]):
            ids = torch.tensor([item["input_ids"]])
            labels = torch.tensor([item["labels"]])
            inputs = {"input_ids": ids, "labels": labels, "attention_mask": torch.ones_like(ids)}
            count = int((labels[:, 1:] != -100).sum().item())
            value = assistant_loss(model, inputs).item()
            numerator += value * count
            denominator += count
            print(json.dumps({"evaluated": index + 1, "total": len(data["validation"]),
                              "seconds": round(time.monotonic() - started, 1)}), flush=True)
    steps = progress["steps_completed"]
    examples = min(progress["data"]["train"]["encoded_rows"] * progress["configuration"]["epochs"],
                   steps * progress["configuration"]["accumulation"])
    report = {**progress, "mode": "lora_candidate", "steps": steps,
              "candidate_validation_loss": numerator / denominator,
              "selected_data_pass_completed": steps == progress["steps_planned"],
              "full_dataset_pass_completed": False,
              "trained_examples": examples,
              "checkpoint_review": str(args.checkpoint),
              "activation_note": "A saved intermediate checkpoint; real generation comparison is required before activation.",
              "review_seconds": round(time.monotonic() - started, 1), "model_activated": False}
    args.output.mkdir(parents=True, exist_ok=True)
    for filename in ("adapter_model.safetensors", "adapter_config.json"):
        shutil.copy2(args.checkpoint / filename, args.output / filename)
    save_json(args.output / "training_report.json", report)
    print(json.dumps({"steps": steps, "trained_examples": examples,
                      "baseline_validation_loss": report["baseline_validation_loss"],
                      "candidate_validation_loss": report["candidate_validation_loss"],
                      "full_dataset_pass_completed": False}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
