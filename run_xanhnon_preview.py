"""Run the isolated Qwen3 GPU application preview at localhost:5002."""
import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage', type=Path, default=Path('D:/XanhNon-auto-training'))
    parser.add_argument('--port', type=int, default=5002)
    parser.add_argument('--profile', choices=['grounded-v15','grounded-v16'], default='grounded-v15')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Choose an unprivileged local port')
    storage = args.storage.resolve()
    preparation = json.loads((storage/'qwen3-4b-instruct-2507-trial/preparation-state.json').read_text(encoding='utf-8'))
    if preparation.get('status') != 'ready_for_evaluation':
        parser.error('The verified trial model is not ready')
    runtime = storage/'qwen3-4b-hardware-20261023/runtime/llama-server.exe'
    if not runtime.is_file() or not Path(preparation['path']).is_file():
        parser.error('The prepared GPU runtime/model is missing')
    from sensor_training_data import digest
    if digest(Path(preparation['path'])) != preparation['sha256']:
        parser.error('The trial model no longer matches its verified checksum')
    preview = storage/('qwen3-4b-app-preview-20261024'+('-v16' if args.profile=='grounded-v16' else ''))
    preview.mkdir(parents=True, exist_ok=True)
    os.environ.update({
        'CHATBOT_BACKEND': 'llama_cpp', 'CHATBOT_GGUF_PATH': preparation['path'],
        'CHATBOT_LLAMA_SERVER': str(runtime), 'CHATBOT_GPU_LAYERS': '99',
        'CHATBOT_CPU_THREADS': '2', 'CHATBOT_MAX_INPUT_TOKENS': '2048',
        'CHATBOT_MAX_NEW_TOKENS': '192', 'CHATBOT_DETAIL_MAX_NEW_TOKENS': '256',
        'CHATBOT_PROMPT_PROFILE': args.profile, 'XANHNON_AUTO_LEARN': '0',
        'XANHNON_LEARNING_DB': str(preview/'questions.sqlite3'),
        'XANHNON_FEEDBACK_DB': str(preview/'feedback.sqlite3'),
    })
    import chatbot
    chatbot.ACTIVE_RELEASE['name'] = 'XanhNon-Qwen3-4B-GPU-'+args.profile+'-preview'
    from app import app
    from chatbot import warm_up_chatbot
    warm_up_chatbot()
    app.run(host='127.0.0.1', port=args.port, debug=False, threaded=True)


if __name__ == '__main__':
    main()
