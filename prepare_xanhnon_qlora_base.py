"""Prepare pinned NF4 weights for a separate 4B LoRA training candidate."""
import argparse
from datetime import datetime
import hashlib
from pathlib import Path
import traceback

from sensor_training_data import digest, download, request, save_json


REPOSITORY = 'unsloth/Qwen3-4B-Instruct-2507-bnb-4bit'
REVISION = 'f12db89cd5156e090618dded9b4367f23f8f3b33'
MODEL_SHA256 = 'f632ab95da1d8f307237094aca7c7dfa9e416b6d2f87bdd8ecda6dadfedb204d'
FILES = ['config.json', 'generation_config.json', 'tokenizer_config.json',
         'tokenizer.json', 'special_tokens_map.json', 'chat_template.jinja',
         'added_tokens.json', 'vocab.json', 'merges.txt', 'README.md', 'model.safetensors']


def prepare(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    state = {'repository': REPOSITORY, 'revision': REVISION, 'model_activated': False,
             'license': 'Apache-2.0', 'base_model': 'Qwen/Qwen3-4B-Instruct-2507',
             'purpose': 'Training-compatible NF4 base; separate from the GGUF preview'}

    def update(**values):
        state.update(values, checked_at=datetime.now().astimezone().isoformat())
        save_json(output / 'preparation-state.json', state)

    try:
        update(status='reading_pinned_metadata')
        with request(f'https://huggingface.co/api/models/{REPOSITORY}/revision/{REVISION}?blobs=true') as response:
            metadata = response.json()
        if metadata['sha'] != REVISION:
            raise ValueError('The publisher revision changed')
        save_json(output / 'upstream-metadata.json', metadata)
        files = {row['rfilename']: row for row in metadata['siblings']}
        if files['model.safetensors']['lfs']['sha256'] != MODEL_SHA256:
            raise ValueError('Unexpected pinned model checksum')
        artifacts = {}
        for name in FILES:
            row = files[name]
            update(status='downloading', current_file=name, current_file_bytes=row['size'],
                   artifacts_sha256=artifacts)
            entry = {'key': name, 'size': row['size'],
                     'url': f'https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{name}'}
            if row.get('lfs'):
                entry['checksum'] = 'sha256:' + row['lfs']['sha256']
            path, action = download(entry, output / name)
            if not row.get('lfs'):
                content = path.read_bytes()
                blob = hashlib.sha1(f'blob {len(content)}\0'.encode() + content).hexdigest()
                if blob != row['blobId']:
                    raise ValueError('Git blob checksum mismatch: ' + name)
            artifacts[name] = digest(path)
            print(f'{name}: {action}', flush=True)
        update(status='ready_for_training', current_file=None, artifacts_sha256=artifacts)
        return state
    except Exception as error:
        update(status='failed', error=str(error))
        (output / 'preparation-error.log').write_text(traceback.format_exc(), encoding='utf-8')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    prepare(parser.parse_args().output)
