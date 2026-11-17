"""Export a trained LoRA candidate, then activate only after answer review."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(part)
    return result.hexdigest()


def resolve_training_base(adapter, explicit=None, root=ROOT):
    if explicit is not None:
        return Path(explicit)
    metadata = Path(adapter)/'adapter_config.json'
    if metadata.is_file():
        name = json.loads(metadata.read_text(encoding='utf-8')).get('base_model_name_or_path')
        if name:
            declared = Path(name)
            if declared.is_dir():
                return declared
            relocated = Path(root)/'models'/declared.name
            if relocated.is_dir():
                return relocated
            raise ValueError('Training base is missing; specify the correct local --base')
    return Path(root)/'models/xanhnon-qwen2.5-0.5b-vietnamese'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--base", type=Path, help="Defaults to the base recorded in adapter_config.json")
    parser.add_argument("--gguf", type=Path, default=ROOT / "models/xanhnon-style-v1-f16.gguf")
    parser.add_argument("--merged", type=Path, default=ROOT / ".runtime/xanhnon-training/style-v1/merged")
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--evaluation", type=Path)
    parser.add_argument("--release-dir", type=Path, default=ROOT / "models/xanhnon-style-lora-v1")
    parser.add_argument("--name", default="Xanh Non — Vietnamese style")
    args = parser.parse_args()
    report = json.loads((args.adapter / "training_report.json").read_text(encoding="utf-8"))
    if report.get("mode") != "lora_candidate" or report.get("steps", 0) < 1:
        parser.error("Adapter has no completed training report")
    try:
        args.base = resolve_training_base(args.adapter, args.base)
    except ValueError as error:
        parser.error(str(error))
    args.gguf = args.gguf.resolve()
    if args.gguf == (ROOT / "models/xanhnon-f16.gguf").resolve():
        parser.error("Choose a new GGUF; preserve the original model")
    if args.activate:
        if not args.gguf.is_relative_to(ROOT / "models"):
            parser.error("Activation requires a GGUF inside models")
        if not args.evaluation or not args.gguf.is_file():
            parser.error("Activation needs an exported GGUF and --evaluation")
        evaluation = json.loads(args.evaluation.read_text(encoding="utf-8"))
        if Path(evaluation["model"]).resolve() != args.gguf:
            parser.error("Evaluation report belongs to another GGUF")
        if not evaluation.get("comparison", {}).get("eligible_for_manual_review"):
            parser.error("Answer comparison contains regressions; candidate is not eligible")
        destination = args.release_dir.resolve()
        if not destination.is_relative_to(ROOT / "models"):
            parser.error("Release directory must remain inside models")
        if (destination / "adapter_model.safetensors").exists() and digest(destination / "adapter_model.safetensors") != digest(args.adapter / "adapter_model.safetensors"):
            parser.error("Release directory contains another adapter; choose a new --release-dir")
        destination.mkdir(parents=True, exist_ok=True)
        for name in ("adapter_config.json", "adapter_model.safetensors", "training_report.json"):
            if (args.adapter / name).resolve() != (destination / name).resolve():
                shutil.copy2(args.adapter / name, destination / name)
        shutil.copy2(args.base / "LICENSE.txt", destination / "LICENSE.txt")
        shutil.copy2(args.evaluation, destination / "evaluation.json")
        active = {"version": 1, "name": args.name,
                  "gguf": args.gguf.relative_to(ROOT).as_posix(),
                  "adapter": destination.relative_to(ROOT).as_posix(),
                  "base_model": args.base.resolve().relative_to(ROOT).as_posix(),
                  "gguf_sha256": digest(args.gguf),
                  "dataset_manifest_sha256": report["manifest_sha256"],
                  "training_steps": report.get("cumulative_steps", report["steps"]),
                  "stage_training_steps": report["steps"], "activated_at": datetime.now(timezone.utc).isoformat()}
        manifest = ROOT / "models/xanhnon-active.json"
        if manifest.exists():
            shutil.copy2(manifest, manifest.with_suffix(".previous.json"))
        temporary = manifest.with_suffix(".json.new")
        temporary.write_text(json.dumps(active, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(manifest)
        print(json.dumps(active, ensure_ascii=False), flush=True)
        return
    if args.gguf.exists() or (args.merged.exists() and any(args.merged.iterdir())):
        parser.error("Export destination already exists; choose new output paths")
    for destination in (args.gguf.parent, args.merged.resolve()):
        existing_parent = destination
        while not existing_parent.exists():
            existing_parent = existing_parent.parent
        if shutil.disk_usage(existing_parent).free < 3 * 2**30:
            parser.error("Export needs at least 3 GiB free disk space at " + str(existing_parent))
    if importlib.util.find_spec("sentencepiece") is None:
        parser.error("Install requirements-train.txt before GGUF export (sentencepiece is required)")
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(4)
    model = AutoModelForCausalLM.from_pretrained(args.base, local_files_only=True, trust_remote_code=False,
                                                dtype=torch.float16, use_safetensors=True, low_cpu_mem_usage=True)
    model = PeftModel.from_pretrained(model, args.adapter, is_trainable=False, local_files_only=True)
    model = model.merge_and_unload(safe_merge=True).to(dtype=torch.float16)
    args.merged.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.merged, safe_serialization=True)
    AutoTokenizer.from_pretrained(args.base, local_files_only=True, use_fast=False).save_pretrained(args.merged)
    del model
    import gc
    gc.collect()
    converter = ROOT / ".runtime/llama-converter/convert_hf_to_gguf.py"
    args.gguf.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(converter), str(args.merged), "--outfile", str(args.gguf),
                    "--outtype", "f16", "--model-name", args.name], check=True)
    print(json.dumps({"gguf": str(args.gguf), "bytes": args.gguf.stat().st_size,
                      "sha256": digest(args.gguf), "activated": False}), flush=True)


if __name__ == "__main__":
    main()
