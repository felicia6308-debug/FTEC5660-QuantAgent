"""Score saved BTC 4h outputs without API calls."""
import csv
import hashlib
import json
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[1]

def evaluate():
    expected = json.loads((ROOT / 'upstream_sha256.json').read_text())
    for name, digest in expected.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Upstream file differs: {name}')
    rows = []
    summaries = {}
    for label, window in [('original', 97), ('window50', 50)]:
        runs = []
        for run in range(1, 4):
            hits = 0
            for sample in range(1, 101):
                filename = f'BTC_4h_{sample}_original_flow_nonthinking.json'
                result = json.loads((ROOT / 'results' / f'btc4h_{label}_run{run}' / filename).read_text())
                if result['status'] != 'completed' or result['input_rows'] != window or result['withheld_rows'] != 3:
                    raise ValueError(f'Invalid result: {label}, run {run}, sample {sample}')
                report = result['reports']['final_trade_decision']
                match = re.search(r'"decision"\s*:\s*"(LONG|SHORT)"', report, re.I)
                if not match:
                    raise ValueError(f'Unparseable decision: {filename}')
                decision = match.group(1).upper()
                with (ROOT / 'QuantHarness-main/benchmark/btc' / f'BTC_4h_{sample}.csv').open() as stream:
                    data = list(csv.DictReader(stream))
                assert len(data) == 100
                anchor = float(data[96]['Close'])
                score = sum(float(row['Close']) > anchor if decision == 'LONG' else float(row['Close']) < anchor for row in data[97:100])
                hits += score
                rows.append([window, run, sample, decision, score, 3])
            runs.append({'run': run, 'valid': 100, 'hits': hits, 'accuracy_percent': hits / 3})
        values = [r['accuracy_percent'] for r in runs]
        summaries[label] = {'runs': runs, 'mean_accuracy_percent': statistics.mean(values),
                            'sample_std_percentage_points': statistics.stdev(values),
                            'sample_variance_percentage_points_squared': statistics.variance(values)}
    directory = ROOT / 'results'
    with (directory / 'directional_scores.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['history_window', 'run', 'sample', 'decision', 'hits', 'targets'])
        writer.writerows(rows)
    (directory / 'evaluation_summary.json').write_text(json.dumps(summaries, indent=2) + '\n')
    print(json.dumps(summaries, indent=2))

if __name__ == '__main__':
    evaluate()
