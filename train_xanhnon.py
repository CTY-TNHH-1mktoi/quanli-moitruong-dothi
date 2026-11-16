"""Validate local SFT data, or explicitly train a separate LoRA candidate.

Default execution checks data only. --train creates an adapter under .runtime;
it never overwrites source weights or automatically promotes a candidate.
"""

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time


ROOT = Path(__file__).resolve().parent
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")


def encode_record(tokenizer, record, max_length):
    messages = record["messages"]
    chosen = None
    for end in range(3, len(messages) + 1, 2):
        tokens = tokenizer.apply_chat_template(messages[:end], tokenize=True, add_generation_prompt=False)
        if len(tokens) > max_length:
            break
        chosen = (messages[:end], tokens)
    if chosen is None:
        return None
    messages, tokens = chosen
    labels = [-100] * len(tokens)
    for index, message in enumerate(messages):
        if message["role"] != "assistant":
            continue
        if record.get("supervise_last_assistant_only") and index != len(messages) - 1:
            continue
        prefix = tokenizer.apply_chat_template(messages[:index], tokenize=True, add_generation_prompt=True)
        complete = tokenizer.apply_chat_template(messages[:index + 1], tokenize=True, add_generation_prompt=False)
        if complete[:len(prefix)] != prefix or tokens[:len(complete)] != complete:
            raise ValueError("Chat template is not prefix-stable; cannot mask assistant labels safely")
        labels[len(prefix):len(complete)] = tokens[len(prefix):len(complete)]
    if not any(label != -100 for label in labels):
        raise ValueError("No assistant target tokens")
    return {"input_ids": tokens, "labels": labels, "id": record["id"], "source": record["source"],
            "messages_used": len(messages), "topic": record.get("topic")}


def read_records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


LORA_MODULES = {'q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'}


def adapter_metadata(directory, target_modules=()):
    modules = list(dict.fromkeys(target_modules))
    if set(modules) - LORA_MODULES:
        raise ValueError('Unsupported LoRA target module')
    if directory is None:
        return {'lora_rank': 8, 'lora_alpha': 16, 'target_modules': modules or ['q_proj', 'v_proj']}
    config = json.loads((Path(directory) / 'adapter_config.json').read_text(encoding='utf-8'))
    if modules and set(modules) != set(config['target_modules']):
        raise ValueError('Requested modules differ from the source adapter')
    return {'lora_rank': config['r'], 'lora_alpha': config['lora_alpha'],
            'target_modules': config['target_modules'], 'effective_layers': config.get('layers_to_transform')}


def verified_nf4_preparation(directory):
    """Reject changed weights/config before opting into CPU NF4 training."""
    from sensor_training_data import digest
    directory = Path(directory)
    state = json.loads((directory / 'preparation-state.json').read_text(encoding='utf-8'))
    if state.get('status') != 'ready_for_training':
        raise ValueError('The NF4 training base has not finished verification')
    artifacts = state.get('artifacts_sha256', {})
    if not {'model.safetensors', 'config.json', 'tokenizer.json', 'tokenizer_config.json'} <= set(artifacts):
        raise ValueError('Incomplete NF4 training provenance')
    for filename, expected in artifacts.items():
        if Path(filename).name != filename or digest(directory / filename) != expected:
            raise ValueError('NF4 training base changed: ' + filename)
    return state


def load_cpu_nf4_model(directory):
    import torch
    from peft import prepare_model_for_kbit_training
    from transformers import AutoConfig, AutoModelForCausalLM
    config = AutoConfig.from_pretrained(directory, local_files_only=True, trust_remote_code=False)
    if not config.quantization_config.get('load_in_4bit'):
        raise ValueError('CPU NF4 training requires prequantized 4-bit weights')
    # Override compute precision in memory; keep the pinned source config intact.
    config.quantization_config = {**config.quantization_config, 'bnb_4bit_compute_dtype': 'float32'}
    model = AutoModelForCausalLM.from_pretrained(
        directory, config=config, device_map={'': 'cpu'}, dtype=torch.float32,
        local_files_only=True, trust_remote_code=False, use_safetensors=True,
        attn_implementation='sdpa',
    )
    if not getattr(model, 'is_loaded_in_4bit', False):
        raise ValueError('The model was not loaded in 4-bit form')
    return prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                                          gradient_checkpointing_kwargs={'use_reentrant': False})


def load_data(tokenizer, max_length, limit=0, validation_limit=0, train_sources=(), data_dir=None):
    data_dir = Path(data_dir) if data_dir is not None else ROOT / "data/xanhnon"
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    for filename, expected in manifest.get("artifacts_sha256", {}).items():
        if hashlib.sha256((data_dir / filename).read_bytes()).hexdigest() != expected:
            raise ValueError("Data files do not match the manifest; finish preparing data before training")
    raw = {name: read_records(data_dir / f"{name}.jsonl")
           for name in ("train", "validation")}
    train_groups = {record["group_id"] for record in raw["train"]}
    validation_groups = {record["group_id"] for record in raw["validation"]}
    if train_groups & validation_groups:
        raise ValueError("Source groups leak between train and validation")
    result, statistics = {}, {}
    for name, records in raw.items():
        if name == "train" and train_sources:
            records = [record for record in records if record["source"] in train_sources]
            if not records:
                raise ValueError("Selected training sources contain no records")
        encoded = []
        for record in records:
            item = encode_record(tokenizer, record, max_length)
            if item and manifest.get("require_complete_dialogues") and item["messages_used"] < len(record["messages"]):
                item = None
            if item is not None:
                encoded.append(item)
        random.Random(42).shuffle(encoded)
        selected_limit = limit if name == "train" else validation_limit
        if selected_limit:
            # Round-robin source sampling keeps a small CPU pilot representative.
            buckets = {}
            for item in encoded:
                buckets.setdefault(item["source"], []).append(item)
            selected = []
            while len(selected) < selected_limit and any(buckets.values()):
                for key in sorted(buckets):
                    if buckets[key] and len(selected) < selected_limit:
                        selected.append(buckets[key].pop())
            encoded = selected
        if not encoded:
            raise ValueError(f"No usable {name} examples; increase --max-length")
        result[name] = encoded
        statistics[name] = {
            "raw_rows": len(records), "encoded_rows": len(encoded),
            "sources": dict(Counter(item["source"] for item in encoded)),
            "topics": dict(Counter(item["topic"] for item in encoded if item.get("topic"))),
            "tokens": sum(len(item["input_ids"]) for item in encoded),
            "assistant_tokens": sum(sum(label != -100 for label in item["labels"]) for item in encoded),
        }
    missing_sources = set(manifest.get("required_train_sources", [])) - set(statistics["train"]["sources"])
    if missing_sources:
        raise ValueError("Required sources have no usable training examples: " + ", ".join(sorted(missing_sources)))
    missing_topics = set(manifest.get("required_train_topics", [])) - set(statistics["train"]["topics"])
    if missing_topics:
        raise ValueError("Required dialogue topics do not fit in the training context: " + ", ".join(sorted(missing_topics)))
    return result, statistics


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".new")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def assistant_loss(model, inputs):
    """Equivalent masked causal loss without projecting unused prompt tokens.

    Qwen2's logits_to_keep selects hidden states BEFORE its large vocabulary
    projection. Batch size is one in this trainer; positions are shifted once
    so logits at t-1 predict the assistant label at t.
    """
    import torch
    labels = inputs["labels"]
    if labels.shape[0] != 1:
        raise ValueError("Assistant-only projection expects batch size one")
    positions = torch.where(labels[0, 1:] != -100)[0]
    if positions.numel() == 0:
        raise ValueError("No assistant tokens after the causal shift")
    outputs = model(input_ids=inputs["input_ids"], attention_mask=inputs["attention_mask"],
                    logits_to_keep=positions, use_cache=False)
    return torch.nn.functional.cross_entropy(outputs.logits[0].float(), labels[0, positions + 1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "xanhnon-qwen2.5-0.5b-vietnamese")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/xanhnon",
                        help="Prepared training data and manifest; default keeps the existing project dataset")
    parser.add_argument("--output", type=Path, default=ROOT / ".runtime" / "xanhnon-training" / "candidate")
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--max-steps", type=int, default=0, help="0 trains all examples for the configured epochs")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--validation-limit", type=int, default=0)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--accumulation", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=0.0001)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--last-layers", type=int, default=0, help="0 adapts all layers; a positive value adapts only the final N layers")
    parser.add_argument("--checkpoint-every", type=int, default=25)
    parser.add_argument("--adapter", type=Path, help="Continue learning from an existing LoRA adapter")
    parser.add_argument('--resume-from', type=Path, help='Recover the same training plan from a saved checkpoint')
    parser.add_argument('--allow-optimizer-reset', action='store_true',
                        help='Explicitly recover an older weights-only checkpoint without its optimizer/RNG state')
    parser.add_argument("--train-source", action="append", default=[], help="Train only these sources; validation remains unchanged")
    parser.add_argument("--allow-cpu-paging", action="store_true", help="Allow Windows paging when RAM is tight and at least 6 GiB RAM+swap remain")
    parser.add_argument('--cpu-nf4', action='store_true',
                        help='Train a verified prequantized NF4 base on CPU; dependencies must support CPU backward')
    parser.add_argument('--target-module', action='append', default=[], choices=sorted(LORA_MODULES),
                        help='Repeat to choose LoRA projections for a new adapter; default remains q_proj/v_proj')
    args = parser.parse_args()
    if args.resume_from and args.adapter:
        parser.error('Choose --resume-from or --adapter, not both')
    if args.allow_optimizer_reset and not args.resume_from:
        parser.error('--allow-optimizer-reset requires --resume-from')
    if args.resume_from:
        args.adapter = args.resume_from
    if min(args.max_length, args.epochs, args.accumulation, args.threads) < 1 or min(args.max_steps, args.limit, args.validation_limit, args.last_layers, args.checkpoint_every) < 0:
        parser.error("Lengths/epochs/accumulation/threads must be positive; limits must be nonnegative")
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True, trust_remote_code=False, use_fast=False)
    data, statistics = load_data(tokenizer, args.max_length, args.limit, args.validation_limit, args.train_source, args.data_dir)
    report = {"mode": "data_check", "max_length": args.max_length, "data": statistics,
              "configuration": {"limit": args.limit, "validation_limit": args.validation_limit,
                                "max_steps": args.max_steps, "epochs": args.epochs,
                                "accumulation": args.accumulation, "learning_rate": args.learning_rate,
                                "seed": 42, "lora_rank": 8, "lora_alpha": 16,
                                "last_layers": args.last_layers, "checkpoint_every": args.checkpoint_every,
                                "source_adapter": str(args.adapter) if args.adapter else None},
              "data_dir": str(args.data_dir.resolve()),
              "manifest_sha256": hashlib.sha256((args.data_dir / "manifest.json").read_bytes()).hexdigest(),
              "model_activated": False}
    report["configuration"]["train_sources"] = args.train_source
    report['configuration'].update(adapter_metadata(args.adapter, args.target_module))
    if args.cpu_nf4:
        preparation = verified_nf4_preparation(args.model)
        report['configuration'].update(quantization='bitsandbytes_nf4_cpu_float32_compute',
            base_model_sha256=preparation['artifacts_sha256']['model.safetensors'],
            base_model_revision=preparation['revision'])
    rows = data['train'] * args.epochs
    total_steps = math.ceil(len(rows) / args.accumulation)
    if args.max_steps:
        total_steps = min(total_steps, args.max_steps)
    from training_resume import order_hash, resume_plan, save_trainer_state, restore_trainer_state
    fingerprint = order_hash(rows)
    report['training_order_sha256'] = fingerprint
    previous, recovery = None, None
    start_step = 0
    if args.resume_from:
        previous, recovery = resume_plan(args.resume_from, report, rows, total_steps,
                                         allow_optimizer_reset=args.allow_optimizer_reset)
        start_step = recovery['checkpoint_step']
        report['recovery'] = recovery
    print(json.dumps(report, ensure_ascii=False), flush=True)
    if not args.train:
        save_json(ROOT / ".runtime" / "xanhnon-data" / "preflight.json", report)
        return
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Output directory is not empty; choose another --output to preserve previous candidates")

    import torch
    import psutil
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import AutoModelForCausalLM
    torch.manual_seed(42)
    torch.set_num_threads(args.threads)
    device = 'cpu' if args.cpu_nf4 else ("cuda" if torch.cuda.is_available() else "cpu")
    available_gb = psutil.virtual_memory().available / 2**30
    required_gb = 2.1 if 0 < args.last_layers <= 8 and args.max_length <= 512 else 2.5
    if args.cpu_nf4:
        required_gb = 4.2
    paging_gb = (psutil.virtual_memory().available + psutil.swap_memory().free) / 2**30
    paging_allowed = args.allow_cpu_paging and paging_gb >= 6
    report["configuration"].update({"allow_cpu_paging": args.allow_cpu_paging,
                                    "available_ram_gb_at_start": round(available_gb, 2)})
    if device == "cpu" and available_gb < required_gb and not paging_allowed:
        report.update({"mode": "training_not_started", "reason": "insufficient_available_ram",
                       "available_ram_gb": round(available_gb, 2)})
        save_json(args.output / "training_report.json", report)
        parser.error(f"CPU training needs at least {required_gb:g} GiB available RAM; free memory first")
    dtype = torch.float32 if device == "cpu" else torch.float16
    from training_state import register_training
    register_training(os.getpid(), args.output)
    if args.cpu_nf4:
        save_json(args.output / 'progress.json', {**report, 'mode': 'lora_training',
            'phase': 'loading_model', 'steps_completed': start_step, 'steps_planned': total_steps})
        model = load_cpu_nf4_model(args.model)
    else:
        model = AutoModelForCausalLM.from_pretrained(
            args.model, local_files_only=True, trust_remote_code=False, use_safetensors=True,
            dtype=dtype, attn_implementation="sdpa",
        ).to(device)
    if args.adapter:
        model = PeftModel.from_pretrained(model, args.adapter, is_trainable=True)
    else:
        layers = list(range(max(0, model.config.num_hidden_layers - args.last_layers),
                            model.config.num_hidden_layers)) if args.last_layers else None
        model = get_peft_model(model, LoraConfig(
            task_type="CAUSAL_LM", r=8, lora_alpha=16, lora_dropout=0.05,
            target_modules=report['configuration']['target_modules'], layers_to_transform=layers, bias="none",
        ))
    model.config.use_cache = False
    if device == "cpu":
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})

    def batch(item):
        ids = torch.tensor([item["input_ids"]], device=device)
        labels = torch.tensor([item["labels"]], device=device)
        return {"input_ids": ids, "attention_mask": torch.ones_like(ids), "labels": labels}

    def evaluate():
        model.eval()
        numerator, denominator = 0.0, 0
        with torch.no_grad():
            for item in data["validation"]:
                inputs = batch(item)
                count = int((inputs["labels"][:, 1:] != -100).sum().item())
                value = assistant_loss(model, inputs).item()
                numerator += value * count
                denominator += count
        return numerator / denominator

    started = time.monotonic()
    report.update({"mode": "lora_training", "phase": "baseline_validation", "device": device, "steps_completed": start_step,
                   'steps_planned': total_steps,
                   "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad)})
    args.output.mkdir(parents=True, exist_ok=True)
    save_json(args.output / "progress.json", report)
    initial_loss = evaluate()
    baseline_loss = previous['baseline_validation_loss'] if previous else initial_loss
    if recovery:
        report['resume_checkpoint_validation_loss'] = initial_loss
    report["baseline_validation_loss"] = baseline_loss
    save_json(args.output / "progress.json", report)
    print(json.dumps({"baseline_validation_loss": baseline_loss, "device": device}), flush=True)
    report['phase'] = 'training'
    model.train()
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=args.learning_rate)
    # Mixed precision is only enabled on CUDA. CPU stays in stable float32.
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
    losses = []
    loss_offset = start_step
    if recovery and recovery['optimizer_state_available']:
        losses, loss_offset = restore_trainer_state(args.resume_from, optimizer, scaler, start_step, fingerprint)
    for step in range(start_step, total_steps):
        chunk = rows[step * args.accumulation:(step + 1) * args.accumulation]
        optimizer.zero_grad(set_to_none=True)
        step_loss = 0.0
        for item in chunk:
            with torch.autocast(device_type=device, dtype=torch.float16, enabled=device == "cuda"):
                loss = assistant_loss(model, batch(item))
            if not torch.isfinite(loss):
                raise RuntimeError("Non-finite training loss; candidate has not been activated")
            step_loss += loss.item() / len(chunk)
            scaler.scale(loss / len(chunk)).backward()
        scaler.unscale_(optimizer)
        grad_norm = torch.nn.utils.clip_grad_norm_((p for p in model.parameters() if p.requires_grad), 1.0)
        if not torch.isfinite(grad_norm) or (args.cpu_nf4 and grad_norm.item() == 0):
            raise RuntimeError('No finite, nonzero adapter gradient; candidate has not been activated')
        scaler.step(optimizer)
        scaler.update()
        losses.append(step_loss)
        elapsed = time.monotonic() - started
        progress = {**report, "steps_completed": step + 1, "steps_planned": total_steps,
                    'stage_steps_completed': step + 1 - start_step,
                    "latest_loss": round(step_loss, 5), "elapsed_seconds": round(elapsed, 1),
                    'gradient_norm': float(grad_norm.item()),
                    "available_ram_gb": round(psutil.virtual_memory().available / 2**30, 2),
                    "process_ram_gb": round(psutil.Process().memory_info().rss / 2**30, 2)}
        save_json(args.output / "progress.json", progress)
        print(json.dumps({key: progress[key] for key in ("steps_completed", "steps_planned", "latest_loss", "elapsed_seconds", "process_ram_gb")}), flush=True)
        if args.checkpoint_every and (step + 1) % args.checkpoint_every == 0:
            checkpoint = args.output / "checkpoints" / f"step-{step + 1:04d}"
            model.save_pretrained(checkpoint, safe_serialization=True)
            save_trainer_state(checkpoint / 'trainer-state.pt', optimizer, scaler,
                               step+1, losses, loss_offset, fingerprint)
            save_json(checkpoint / "progress.json", progress)
    save_json(args.output / 'progress.json', {**progress, 'phase': 'final_validation'})
    candidate_loss = evaluate()
    args.output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.output, safe_serialization=True)
    tokenizer.save_pretrained(args.output)
    report.update({"mode": "lora_candidate", "phase": "awaiting_answer_review", "device": device, "steps": total_steps, "steps_completed": total_steps,
                   "selected_data_pass_completed": total_steps == math.ceil(len(rows) / args.accumulation),
                   "full_dataset_pass_completed": not args.limit and not args.train_source and statistics["train"]["encoded_rows"] == statistics["train"]["raw_rows"] and total_steps == math.ceil(len(rows) / args.accumulation),
                   "trained_examples": min(len(rows), total_steps * args.accumulation),
                   'stage_training_steps': total_steps-start_step,
                   'stage_trained_examples': min(len(rows), total_steps*args.accumulation)-start_step*args.accumulation,
                   'loss_step_offset': loss_offset,
                   "baseline_validation_loss": baseline_loss, "candidate_validation_loss": candidate_loss,
                   "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
                   "elapsed_seconds": round(time.monotonic() - started, 1), "losses": losses,
                   "activation_note": "Requires separate answer-quality evaluation and merge/GGUF conversion before deployment."})
    save_json(args.output / "training_report.json", report)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
