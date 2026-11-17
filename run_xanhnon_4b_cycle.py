"""Run and monitor one isolated 4B corrective adapter training job."""
import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

from sensor_training_data import ROOT, digest, save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage',type=Path,default=Path('D:/XanhNon-auto-training'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--learning-rate',type=float,default=0.00002)
    parser.add_argument('--accumulation',type=int,default=4)
    parser.add_argument('--max-length',type=int,default=768)
    parser.add_argument('--target-module',action='append',default=[])
    parser.add_argument('--allow-cpu-paging',action='store_true')
    parser.add_argument('--review-after',action='store_true',help='Export and compare frozen v16 pilot cases after training')
    args = parser.parse_args()
    if args.accumulation < 1 or args.max_length < 1 or args.learning_rate <= 0:
        parser.error('Invalid pilot configuration')
    output, candidate, storage = args.output.resolve(), args.candidate.resolve(), args.storage.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('Choose a new cycle directory to preserve previous evidence')
    if candidate.exists() and any(candidate.iterdir()):
        parser.error('Choose a new candidate directory')
    output.mkdir(parents=True,exist_ok=True)
    env = os.environ.copy()
    env.update(PYTHONPATH=str(storage/'qlora-runtime'),USE_TF='0',USE_FLAX='0')
    data = args.data_dir.resolve() if args.data_dir else storage/'qwen3-4b-correction-data-20261024'
    manifest = json.loads((data/'manifest.json').read_text(encoding='utf-8'))
    train_count = len([line for line in (data/'train.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()])
    if args.review_after and manifest.get('prompt_profile') != 'grounded-v16':
        parser.error('Automatic pilot review requires frozen v16 evidence and cases')
    command = [sys.executable,'-u',str(ROOT/'train_xanhnon.py'),'--train',
        '--model',str(storage/'qwen3-4b-nf4-training-base'),'--data-dir',str(data),
        '--output',str(candidate),'--max-length',str(args.max_length),'--epochs','1','--accumulation',str(args.accumulation),
        '--learning-rate',str(args.learning_rate),'--threads','2','--last-layers','4','--checkpoint-every','1','--cpu-nf4']
    if args.allow_cpu_paging:
        command.append('--allow-cpu-paging')
    for module in args.target_module:
        command += ['--target-module',module]
    frozen = output/'scripts'
    frozen.mkdir()
    recipes = ['train_xanhnon.py','training_resume.py','prepare_xanhnon_4b_corrections.py',
               'chat_briefing.py','chat_briefing_v15.py','run_xanhnon_4b_cycle.py']
    if args.review_after:
        recipes += ['chat_briefing_v16.py','chat_scope.py','prepare_xanhnon_v16_pilot.py',
                    'review_xanhnon_v16_signal.py','native_chatbot.py','review_xanhnon_4b_lora.py',
                    'evaluate_xanhnon.py','chat_answer_checks.py']
        for name in manifest.get('input_sha256', {}):
            if Path(name).name == name and name.endswith('.py') and (ROOT/name).is_file() and name not in recipes:
                recipes.append(name)
    hashes = {}
    for name in recipes:
        shutil.copy2(ROOT/name,frozen/name)
        hashes[name] = digest(frozen/name)
    state = {'worker_pid':os.getpid(),'candidate':str(candidate),'data_dir':str(data),
             'model_activated':False,'command':command,'script_sha256':hashes,
             'data_manifest_sha256':digest(data/'manifest.json'),'steps_planned':math.ceil(train_count/args.accumulation),
             'review_after_training':args.review_after,
             'started_at':datetime.now().astimezone().isoformat()}

    def update(**values):
        state.update(values,checked_at=datetime.now().astimezone().isoformat())
        save_json(output/'cycle-state.json',state)

    try:
        with (output/'training.log').open('w',encoding='utf-8',buffering=1) as log:
            process = subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            update(status='running',phase='trainer_starting',trainer_launcher_pid=process.pid)
            while process.poll() is None:
                progress_path = candidate/'progress.json'
                if progress_path.is_file():
                    progress = json.loads(progress_path.read_text(encoding='utf-8'))
                    update(phase=progress.get('phase'),steps_completed=progress.get('steps_completed',0),
                        latest_loss=progress.get('latest_loss'),gradient_norm=progress.get('gradient_norm'),
                        available_ram_gb=progress.get('available_ram_gb'))
                time.sleep(10)
            if process.returncode != 0:
                update(status='failed',phase='training_failed',returncode=process.returncode,
                       error='Trainer failed; see training.log. Existing release was preserved.')
                return
        report = json.loads((candidate/'training_report.json').read_text(encoding='utf-8'))
        if report.get('mode') != 'lora_candidate' or not report.get('full_dataset_pass_completed'):
            raise ValueError('Training did not finish the prepared batch')
        update(status='awaiting_answer_evaluation',phase='training_finished',
            steps_completed=report['steps_completed'],baseline_validation_loss=report['baseline_validation_loss'],
            candidate_validation_loss=report['candidate_validation_loss'],
            adapter_sha256=digest(candidate/'adapter_model.safetensors'),
            warning='Loss is not answer accuracy. No candidate has been deployed.')
        if args.review_after:
            review = output/'answer-review'
            review_command = [sys.executable,'-u',str(ROOT/'review_xanhnon_v16_signal.py'),
                '--storage',str(storage),'--candidate',str(candidate),'--data-dir',str(data),'--output',str(review)]
            update(status='running',phase='answer_evaluation',review_state=str(review/'review-state.json'))
            with (output/'review.log').open('w',encoding='utf-8') as log:
                result = subprocess.run(review_command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            if result.returncode:
                raise RuntimeError('Automatic comparison failed; see review.log')
            reviewed = json.loads((review/'review-state.json').read_text(encoding='utf-8'))
            update(status='awaiting_manual_review',phase='answer_comparison_finished',
                comparison=reviewed['comparison'],changed_answers=reviewed['changed_answers'],
                decision=reviewed['decision'])
    except Exception as error:
        update(status='failed',error=str(error))
        (output/'worker-error.log').write_text(traceback.format_exc(),encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
