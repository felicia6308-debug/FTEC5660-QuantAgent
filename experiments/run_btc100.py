"""Independent batch launcher. Author code remains unchanged; each process has isolated chart files."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import signal
import threading
import sys
import time
BASE = Path(__file__).resolve().parent
ROOT = BASE.parent / 'QuantHarness-main'
parser = argparse.ArgumentParser()
parser.add_argument('--timeframe', choices=['1h','4h'], default='1h')
parser.add_argument('--window', type=int, choices=[50,97], default=97)
parser.add_argument('--run', type=int, default=1, choices=range(1,100))
parser.add_argument('--limit', type=int, default=100, choices=range(1,101))
args = parser.parse_args()
DATA = ROOT / ('benchmark/1h/btc' if args.timeframe == '1h' else 'benchmark/btc')
label = 'original' if args.window == 97 else f'window{args.window}'
OUT = BASE / f'btc{args.timeframe}_{label}_run{args.run}'
OUT.mkdir(exist_ok=True)
manifest = {'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'model':'deepseek-flash','thinking':'disabled','workers':4,'run':args.run,'history_window':args.window,
            'author_python_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('*.py')},
            'data_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in DATA.glob('*.csv')}}
if not (OUT/'manifest.json').exists():
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
active = set()
lock = threading.Lock()
stopping = threading.Event()
def stop_batch(signum, frame):
    stopping.set()
    with lock:
        for proc in list(active):
            if proc.poll() is None:
                proc.terminate()
    print('Stopped. Completed results are preserved; rerun the command to resume.', flush=True)
    os._exit(130)
signal.signal(signal.SIGINT, stop_batch)
signal.signal(signal.SIGTERM, stop_batch)

def run(i):
    target = OUT / f'BTC_{args.timeframe}_{i}_original_flow_nonthinking.json'
    if stopping.is_set():
        return i, 'stopped'
    if target.exists():
        try:
            if json.loads(target.read_text()).get('status') == 'completed':
                return i, 'existing'
        except (ValueError, OSError):
            pass
        archive = OUT / 'failed_attempts'
        archive.mkdir(exist_ok=True)
        target.rename(archive / f'{target.stem}_{time.time_ns()}.json')
    work=OUT/'work'/str(i); work.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env['MPLCONFIGDIR']='/private/tmp/quant-mpl';env['PYTHONPYCACHEPREFIX']='/private/tmp/quant-pycache'
    with (work/'run.log').open('w') as log:
        proc=subprocess.Popen([sys.executable,str(BASE/'pilot_budget.py'),'--window',str(args.window),'--timeframe',args.timeframe,'--sample',str(i),'--output-dir',str(OUT)],cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT)
        with lock:
            active.add(proc)
        proc.wait()
        with lock:
            active.discard(proc)
    if target.exists():
        return i,json.loads(target.read_text())['status']
    return i,f'process_exit_{proc.returncode}'
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for future in concurrent.futures.as_completed([pool.submit(run,i) for i in range(1,args.limit+1)]):
        print(*future.result(),flush=True)
print('Batch finished',flush=True)
