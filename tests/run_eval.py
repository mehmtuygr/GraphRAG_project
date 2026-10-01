"""Resumable local-only evaluation. Scores are reviewed separately, not guessed."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.request import build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_local import validate_local_config
from scripts.query_process import run_query_process


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='eval/results/pilot-v1')
    parser.add_argument('--methods', nargs='+', choices=['basic','local','global','drift'], default=['basic','local','global','drift'])
    parser.add_argument('--questions', nargs='+')
    parser.add_argument('--timeout', type=int, default=900)
    args = parser.parse_args()
    validate_local_config()
    with build_opener(ProxyHandler({})).open('http://127.0.0.1:11434/api/tags', timeout=10) as response:
        installed = {m['name'] for m in json.load(response)['models']}
    assert {'udl-qwen-local:latest','embeddinggemma:latest'} <= installed, 'Required local models missing'
    dataset_path = ROOT / 'tests/eval_questions.json'
    dataset = json.loads(dataset_path.read_text(encoding='utf-8'))
    out = (ROOT / args.out).resolve()
    if not out.is_relative_to(ROOT):
        raise ValueError('Results must remain within this project')
    out.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(dataset_path.read_bytes() + (ROOT/'settings.yaml').read_bytes()).hexdigest()
    manifest_path = out / 'manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['fingerprint'] != fingerprint:
            raise ValueError('Dataset/config changed; select a new output directory')
    else:
        manifest = {'started_utc':datetime.now(timezone.utc).isoformat(), 'fingerprint':fingerprint,
                    'python':sys.version, 'graphrag':importlib.metadata.version('graphrag'),
                    'global_mode':'full reports', 'community_level':0, 'timeout_seconds':args.timeout,
                    'note':'Sequential queries, one trial each, warm/cold models and existing cache not controlled. No model-based judge.'}
        manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        (out/'settings.snapshot.yaml').write_bytes((ROOT/'settings.yaml').read_bytes())
        (out/'questions.snapshot.json').write_bytes(dataset_path.read_bytes())
    questions = [q for q in dataset['questions'] if not args.questions or q['id'] in args.questions]
    total = len(questions)*len(args.methods)
    for qi,q in enumerate(questions):
        for mi,method in enumerate(args.methods):
            path = out/f"{q['id']}-{method}.json"
            if path.exists():
                print('SKIP',path.stem,flush=True)
                continue
            print(f"START {qi*len(args.methods)+mi+1}/{total} {path.stem}",flush=True)
            env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1', GRADIO_ANALYTICS_ENABLED='False')
            cmd = [sys.executable,str(ROOT/'scripts/run_local.py'),'query',q['question']+'\n\n'+dataset['instruction'],
                   '--method',method,'--community-level','0','--response-type','Multiple Paragraphs']
            if method == 'global':
                cmd.append('--full-reports')
            start = time.monotonic()
            try:
                result = run_query_process(cmd,timeout=args.timeout,cwd=ROOT,env=env)
                record = {'status':'ok' if result.returncode == 0 else 'error','returncode':result.returncode,
                          'answer':result.stdout.strip(),'stderr':result.stderr}
            except subprocess.TimeoutExpired:
                record = {'status':'timeout','answer':'','stderr':'Query exceeded the configured deadline; process tree terminated.'}
            record.update(question_id=q['id'],method=method,seconds=round(time.monotonic()-start,2),
                          finished_utc=datetime.now(timezone.utc).isoformat())
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
            temporary.replace(path)
            print('DONE',path.stem,record['status'],record['seconds'],'seconds',flush=True)
    print('Evaluation queries finished. Answers still require source-based review.',flush=True)


if __name__ == '__main__':
    main()
