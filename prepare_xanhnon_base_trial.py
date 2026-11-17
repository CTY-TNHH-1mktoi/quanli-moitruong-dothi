"""Download one pinned, checksum-verified base-model trial without activating it."""
import argparse
from datetime import datetime
from pathlib import Path
import traceback
from zoneinfo import ZoneInfo

from sensor_training_data import download, request, save_json


REPOSITORY = 'unsloth/Qwen3-4B-Instruct-2507-GGUF'
REVISION = 'a06e946bb6b655725eafa393f4a9745d460374c9'
FILENAME = 'Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
CHECKSUM = '3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
SIZE = 2497281120
UPSTREAM = 'Qwen/Qwen3-4B-Instruct-2507'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    state = {'model_activated': False, 'repository': REPOSITORY, 'revision': REVISION,
             'filename': FILENAME, 'sha256': CHECKSUM, 'size': SIZE, 'upstream': UPSTREAM,
             'license': 'Apache-2.0', 'model_card': 'https://huggingface.co/' + UPSTREAM,
             'path': str(output / FILENAME)}

    def update(**values):
        state.update(values, checked_at=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat())
        save_json(output / 'preparation-state.json', state)

    try:
        update(status='downloading_model')
        entry = {'key': FILENAME, 'size': SIZE, 'checksum': 'sha256:' + CHECKSUM,
                 'url': f'https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{FILENAME}'}
        model, action = download(entry, output / FILENAME)
        update(status='downloading_tokenizer', download_action=action)
        with request(f'https://huggingface.co/api/models/{UPSTREAM}') as response:
            upstream_metadata = response.json()
        revision = upstream_metadata['sha']
        with request(f'https://huggingface.co/api/models/{UPSTREAM}/tree/{revision}?recursive=true&expand=false') as response:
            upstream_files = {item['path']: item for item in response.json() if item['type'] == 'file'}
        selected = ['tokenizer_config.json', 'tokenizer.json', 'config.json', 'generation_config.json', 'LICENSE']
        tokenizer_artifacts = {}
        for name in selected:
            if name not in upstream_files:
                if name in ('tokenizer_config.json', 'tokenizer.json'):
                    raise FileNotFoundError('Missing upstream tokenizer artifact: ' + name)
                continue
            metadata = upstream_files[name]
            item = {'key': name, 'size': metadata['size'],
                    'url': f'https://huggingface.co/{UPSTREAM}/resolve/{revision}/{name}'}
            if metadata.get('lfs', {}).get('oid'):
                item['checksum'] = 'sha256:' + metadata['lfs']['oid']
            path, _ = download(item, output / name)
            from sensor_training_data import digest
            tokenizer_artifacts[name] = digest(path)
        update(status='ready_for_evaluation', tokenizer_revision=revision,
               tokenizer_artifacts_sha256=tokenizer_artifacts, verified_model=str(model))
    except Exception as error:
        update(status='failed', error=str(error))
        (output / 'error.log').write_text(traceback.format_exc(), encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
