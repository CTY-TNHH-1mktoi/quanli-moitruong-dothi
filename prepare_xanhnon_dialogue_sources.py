"""Prepare an isolated, attributed Vietnamese dialogue pool from cached sources.

No training, application changes, or automatic knowledge-base ingestion occurs.
Upstream answers pass heuristics only; they are not verified environmental facts.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import random
import re
import shutil

from chat_learning import _sensitive
from evaluate_xanhnon import evaluation_cases
from prepare_xanhnon_data import (CACHE_DIR, UPSTREAM, assign_split_groups,
                                  filtered_messages, make_record, normalize, stable_id)
from sensor_training_data import ROOT, digest, save_json


DEFAULT_CACHE = Path('D:/XanhNon-auto-training/dialogue-sources-20261021')
SOURCES = {
    'aya': ('CohereLabs/aya_dataset', 'apache-2.0'),
    'wildchat': ('allenai/WildChat-1M', 'odc-by'),
    'oasst2': ('OpenAssistant/oasst2', 'apache-2.0'),
    'seadialogues': ('SEACrowd/SEADialogues', 'cc-by-sa-4.0'),
    'vietverse': ('TTP01/Vietverse-SFT-Preview', 'apache-2.0'),
}
DOMAIN = re.compile(r'\b(aqi|pm25|pm10|moi truong|o nhiem|tai che|rac thai|khi hau|'
                    r'tiet kiem (dien|nuoc)|khong khi|bui min|tieng on|do am|nom am)\b')
PERSONA = re.compile(r'\b(?:toi|minh|em|anh)\s+(?:la (?:bac si|nhan vien|giao vien)|'
                     r'da (?:tung |di |den |song |lam viec)|nho lan|co (?:gia dinh|con nho))\b')
VIETNAMESE_MARKS = set('ăâđêôơưáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ')


def pair_keys(messages):
    return {stable_id(normalize(json.dumps(messages[i:i + 2], ensure_ascii=False, sort_keys=True)))
            for i in range(0, len(messages), 2)}


def filter_dialogue(messages, *, multi, heldout):
    # Check all raw turns, including any suffix outside the selected short prefix.
    if any(not isinstance(m, dict) or not isinstance(m.get('content'), str) for m in messages):
        return None, 'invalid_messages'
    if _sensitive('\n'.join(m['content'] for m in messages)):
        return None, 'sensitive_or_injection'
    if any(normalize(m['content']) in heldout for m in messages if m.get('role') == 'user'):
        return None, 'heldout_question'
    kept, reason = filtered_messages({'messages': messages},
                                     'vietnamese_multiturn' if multi else 'vietnamese_chatting')
    if reason:
        return None, reason
    if any(not (set(m['content'].lower()) & VIETNAMESE_MARKS)
           and normalize(m['content']).strip('.! ') not in ('ok', 'okay', 'oki')
           for m in kept if m['role'] == 'assistant'):
        return None, 'non_vietnamese_assistant_turn'
    if any(PERSONA.search(normalize(m['content'])) for m in kept if m['role'] == 'assistant'):
        return None, 'invented_assistant_experience'
    if DOMAIN.search(normalize(' '.join(m['content'] for m in kept))):
        return None, 'environment_answer_needs_source_review'
    return kept, None


def dialogue_skills(messages):
    skills = []
    if len(messages) > 2:
        skills.append('multi_turn')
    if any('?' in m['content'] for m in messages if m['role'] == 'assistant'):
        skills.append('asks_question')
    if any(re.search(r'^(?:no|vay|the|con|dieu do|cai do)\b', normalize(m['content']))
           for m in messages[2:] if m['role'] == 'user'):
        skills.append('followup_reference')
    if any(re.search(r'\b(?:viet lai|ngan gon|rut gon|noi ro|de hieu|giai thich them)\b', normalize(m['content']))
           for m in messages if m['role'] == 'user'):
        skills.append('adapts_explanation')
    return skills or ['short_qa']


def source_manifest(cache, source):
    directory = cache / source
    manifest = json.loads((directory / 'download-manifest.json').read_text(encoding='utf-8'))
    repo, license_name = SOURCES[source]
    if manifest['repo'] != repo:
        raise ValueError('Unexpected source repository: ' + source)
    if manifest.get('license') not in (None, license_name):
        raise ValueError('Source license changed: ' + source)
    for artifact in manifest['files']:
        if digest(Path(artifact['file'])) != artifact['sha256']:
            raise ValueError('Cached source hash mismatch: ' + artifact['file'])
    return {**manifest, 'license': license_name, 'url': 'https://huggingface.co/datasets/' + repo}


def parquet_dialogues(cache, source, counts):
    import pyarrow.parquet as pq
    path = next((cache / source).glob('*.parquet'))
    columns = (['inputs', 'targets', 'language_code'] if source == 'aya' else
               ['conversation_hash', 'conversation', 'language', 'toxic', 'redacted'])
    for batch in pq.ParquetFile(path).iter_batches(batch_size=512, columns=columns, use_threads=False):
        for row in batch.to_pylist():
            counts['raw_rows'] += 1
            if row.get('language_code') != 'vie' and row.get('language') != 'Vietnamese':
                continue
            counts['vietnamese_rows'] += 1
            if source == 'aya':
                messages = [{'role': 'user', 'content': row['inputs']},
                            {'role': 'assistant', 'content': row['targets']}]
                yield stable_id(json.dumps(messages, ensure_ascii=False)), messages
            else:
                if row.get('toxic') or row.get('redacted'):
                    counts['flagged_or_redacted'] += 1
                    continue
                # Drop IP hashes, headers, user IDs, timestamps, and location metadata.
                yield row['conversation_hash'], [
                    {'role': m['role'], 'content': m['content']} for m in row['conversation']]


def oasst_dialogues(cache, counts):
    nodes = {}
    path = cache / 'oasst2/2023-11-05_oasst2_ready.messages.jsonl.gz'
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            counts['raw_messages'] += 1
            if row.get('lang') == 'vi':
                nodes[row['message_id']] = row
    counts['vietnamese_messages'] = len(nodes)
    for node in nodes.values():
        if node['role'] != 'assistant':
            continue
        chain, seen = [], set()
        current = node
        while current and current['message_id'] not in seen:
            seen.add(current['message_id'])
            chain.append(current)
            current = nodes.get(current.get('parent_id'))
        chain.reverse()
        if not chain or chain[0].get('parent_id'):
            counts['missing_root'] += 1
            continue
        if any(not n.get('review_result') or n.get('deleted') for n in chain):
            counts['not_accepted'] += 1
            continue
        assistants = [n for n in chain if n['role'] == 'assistant']
        if any(n.get('rank') not in (None, 0) for n in assistants):
            counts['not_best_branch'] += 1
            continue
        def bad_labels(n):
            labels = n.get('labels') or {}
            return (labels.get('quality', {}).get('value', 0) < .7 or
                    any(labels.get(k, {}).get('value', 0) > 0 for k in
                        ['pii', 'spam', 'lang_mismatch', 'not_appropriate', 'hate_speech',
                         'sexual_content', 'violence']) or
                    labels.get('toxicity', {}).get('value', 0) > .2)
        if any(bad_labels(n) for n in chain):
            counts['quality_labels'] += 1
            continue
        yield chain[0]['message_id'], [
            {'role': 'user' if n['role'] == 'prompter' else 'assistant', 'content': n['text']}
            for n in chain]


def known_pairs(storage):
    directories = [ROOT / 'data/xanhnon', storage / 'sensor-dataset']
    directories += [p for p in storage.glob('*data-*') if p.is_dir() and (p / 'train.jsonl').exists()]
    pairs, files = set(), {}
    for directory in directories:
        for split in ['train', 'validation']:
            path = directory / (split + '.jsonl')
            if not path.exists():
                continue
            files[str(path)] = digest(path)
            for line in path.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    pairs.update(pair_keys(json.loads(line)['messages'][1:]))
    return pairs, files


def prepare(cache, output, maximum=400, max_length=1024):
    cache, output = Path(cache), Path(output)
    generator_hash = digest(Path(__file__))
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use an empty output directory; prior data is immutable')
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(ROOT / 'models/xanhnon-qwen2.5-0.5b-vietnamese',
                                              local_files_only=True, use_fast=False)
    cases, case_hash = evaluation_cases(ROOT / 'data/xanhnon/eval_consultation.json')
    heldout = {normalize(case['question']) for case in cases}
    heldout.update(normalize(turn['content']) for case in cases for turn in case.get('history', [])
                   if turn['role'] == 'user')
    existing, known_artifacts = known_pairs(cache.parent)
    reports, records, pool_pairs = [], [], set()
    inputs = []
    for source in ['aya', 'wildchat', 'oasst2']:
        manifest = source_manifest(cache, source)
        counts = Counter()
        iterator = (oasst_dialogues(cache, counts) if source == 'oasst2' else
                    parquet_dialogues(cache, source, counts))
        inputs.append((source, manifest, counts, iterator))
    original_manifest = json.loads((ROOT / 'data/xanhnon/manifest.json').read_text(encoding='utf-8'))
    for upstream in UPSTREAM:
        source = upstream['id']
        manifest = next(s for s in original_manifest['sources'] if s['id'] == source)
        path = CACHE_DIR / upstream['file']
        if digest(path) != manifest['raw_sha256']:
            raise ValueError('Original cached dataset changed: ' + source)
        text = path.read_text(encoding='utf-8-sig')
        raw = ([json.loads(line) for line in text.splitlines() if line.strip()]
               if path.suffix == '.jsonl' else json.loads(text))
        def upstream_rows(rows):
            for index, row in enumerate(rows):
                messages = row.get('messages')
                if messages is None:
                    messages = [{'role': {'human': 'user', 'gpt': 'assistant'}.get(m.get('from')),
                                 'content': m.get('value')} for m in row.get('conversations', [])]
                yield str(row.get('id', index)), messages
        inputs.append((source, manifest, Counter(raw_rows=len(raw)), upstream_rows(raw)))
    for source, manifest, counts, iterator in inputs:
        eligible = []
        for original_id, messages in iterator:
            multi = source in ('wildchat', 'vietnamese_multiturn')
            kept, reason = filter_dialogue(messages, multi=multi, heldout=heldout)
            if reason:
                counts[reason] += 1
                continue
            keys = pair_keys(kept)
            if keys & existing:
                counts['already_present_pair'] += 1
                continue
            if keys & pool_pairs:
                counts['duplicate_pool_pair'] += 1
                continue
            row = make_record(kept, 'dialogue_' + source, original_id, topic='multi_turn' if len(kept) > 2 else 'short_qa',
                              license=manifest['license'], upstream_repo=manifest['repo'],
                              upstream_revision=manifest['revision'], upstream_id=original_id,
                              review='automatic_rules_only', knowledge_eligible=False,
                              learning_use='Vietnamese style and dialogue context; not verified domain knowledge',
                              selected_complete_prefix=True, original_message_count=len(messages))
            row['skills'] = dialogue_skills(kept)
            count = len(tokenizer.apply_chat_template(row['messages'], tokenize=True, add_generation_prompt=False))
            if count > max_length:
                counts['full_dialogue_exceeds_token_budget'] += 1
                continue
            row['token_count'] = count
            pool_pairs.update(keys)
            eligible.append(row)
        counts['eligible_novel_rows'] = len(eligible)
        random.Random(42).shuffle(eligible)
        eligible.sort(key=lambda row: ('multi_turn' not in row['skills'],
                                      'asks_question' not in row['skills'],
                                      'followup_reference' not in row['skills'],
                                      'adapts_explanation' not in row['skills']))
        source_limit = min(maximum, 100) if source in ('aya', 'vietnamese_chatting') else maximum
        selected = eligible[:source_limit]
        records.extend(selected)
        counts['selected_rows'] = len(selected)
        reports.append({**manifest, 'selection': dict(counts)})
        print(json.dumps({'source': source, 'counts': dict(counts)}, ensure_ascii=False), flush=True)
    assign_split_groups(records)
    partitions = {'train': [], 'validation': []}
    for row in records:
        split = 'validation' if int(stable_id(row['group_id'])[:8], 16) % 10 == 0 else 'train'
        partitions[split].append(row)
    if digest(Path(__file__)) != generator_hash:
        raise ValueError('Preparation recipe changed during this run; rerun with the final recipe')
    output.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for split, rows in partitions.items():
        random.Random(42).shuffle(rows)
        path = output / (split + '.jsonl')
        path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        artifacts[path.name] = digest(path)
    excluded = [
        {**source_manifest(cache, 'seadialogues'), 'decision': 'not_selected',
         'reason': 'Persona-based conversations between fictional humans; not assistant replies. Avoid teaching invented personal memories.'},
        {**source_manifest(cache, 'vietverse'), 'decision': 'not_selected',
         'reason': '118 of 119 assistant turns exceed 100 words; only 10 multi-turn rows; unsuitable for concise dialogue training without separate rewriting/review.'},
        {'repo': 'VTSNLP/vietnamese_curated_dataset', 'decision': 'not_downloaded', 'reason': 'Pretraining text, not dialogue; no declared dataset license in metadata.'},
        {'repo': 'arcee-ai/EvolKit-20k-vi', 'decision': 'not_downloaded', 'reason': 'Predominantly complex single-turn tasks; no declared dataset license in metadata.'},
        {'repo': 'BlossomsAI/vietnamese-conversational-dataset', 'decision': 'not_downloaded', 'reason': 'Mixed large corpus, verbose reasoning prompts in preview and no declared dataset license in metadata.'},
    ]
    result = {'schema_version': 1, 'built_at': datetime.now(timezone.utc).isoformat(), 'seed': 42,
              'purpose': 'New Vietnamese style/context data pool; preparation only',
              'require_complete_dialogues': True, 'max_length': max_length,
              'counts': {split: dict(Counter(row['source'] for row in rows)) for split, rows in partitions.items()},
              'topics': dict(Counter(row['topic'] for row in records)), 'total_rows': len(records),
              'skills': dict(Counter(skill for row in records for skill in row['skills'])),
              'artifacts_sha256': artifacts, 'sources': reports, 'excluded_sources': excluded,
              'deduplication_against': known_artifacts, 'evaluation_cases_sha256': case_hash,
              'generator_sha256': generator_hash, 'model_activated': False,
              'training_started': False, 'automatic_quality_filter_only': True,
              'limitations': ['Upstream answers are not individually fact-checked.',
                              'Environmental answers are excluded pending authoritative source review.',
                              'PII and instruction filters are heuristics, not a privacy guarantee.',
                              'The WildChat survey covers only its first train shard.',
                              'Preparing data does not update model weights or app knowledge.',
                              'Cross-source near-duplicates beyond normalized exact dialogue pairs may remain.']}
    save_json(output / 'manifest.json', result)
    shutil.copy2(ROOT / 'data/xanhnon/LICENSE-APACHE-2.0.txt', output / 'LICENSE-APACHE-2.0.txt')
    if (cache / 'wildchat/LICENSE.md').exists():
        shutil.copy2(cache / 'wildchat/LICENSE.md', output / 'LICENSE-WILDCHAT-ODC-BY.md')
    notice = ['# Vietnamese dialogue source attribution', '',
              'This is a mixed-source derived selection, not a blanket Apache-2.0 relicensing.',
              'Each record retains its source license and revision. External text is not verified environmental knowledge.', '']
    for report in reports:
        notice.extend([f"## {report['repo']}", f"Source: {report['url']}",
                       f"Revision: {report['revision']}", f"Declared license: {report['license']}",
                       f"Selected: {report['selection']['selected_rows']} complete dialogue prefixes.", ''])
    notice += ['## Changes', 'Selected Vietnamese short turns; removed blocked/PII/held-out/already-used pairs; stripped formatting and metadata; added Xanh Non system prompt; grouped train/validation; preserved complete turns.',
               'No external assistant reply was added to knowledge.json.']
    (output / 'NOTICE.md').write_text('\n'.join(notice) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=DEFAULT_CACHE)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-per-source', type=int, default=400)
    args = parser.parse_args()
    if args.max_per_source < 1:
        parser.error('--max-per-source must be positive')
    report = prepare(args.cache, args.output, args.max_per_source)
    print(json.dumps({key: report[key] for key in ['total_rows', 'counts', 'topics', 'training_started']}, ensure_ascii=False))
