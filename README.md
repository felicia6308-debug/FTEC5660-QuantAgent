# QuantAgent: BTC 4h Reproduction

Reproduction of the BTC 4h directional-accuracy result in Table 1 of [QuantAgent, v3](https://arxiv.org/html/2509.09995v3), followed by a history-window parameter change from 97 to 50 candles. Both conditions use DeepSeek Flash and predict the same final three candles.

## Contents

- `QuantHarness-main/`: unchanged author Python files and MIT license.
- `benchmark.zip`: the 100 BTC 4h benchmark segments; `prepare.py` extracts them into the author data path.
- `experiments/pilot_budget.py`: DeepSeek adapter, input-window selection, and request/usage logging.
- `experiments/run_btc100.py`: four-worker batch launcher, separate chart directories, and resume support.
- `experiments/evaluate.py`: offline scoring of saved outputs.
- `results.zip`: 600 completed sample outputs across two settings and three runs, per-sample scores, and aggregate results.
- `upstream_sha256.json`: checksums of the included author files and data.
- `requirements.txt`: frozen Python environment used for the runs.

Upstream source: [Y-Research-SBU/QuantHarness](https://github.com/Y-Research-SBU/QuantHarness). Author files are copied unchanged; the web interface and unrelated benchmark datasets are omitted. The license is retained in `QuantHarness-main/LICENSE`.

## Installation

Use Python 3.12 (experiment version: 3.12.14). Extract the benchmark data and saved outputs from the repository root first:

```bash
python3 prepare.py
```

Then create the environment:

```bash
python3.12 -m venv .venv312
source .venv312/bin/activate
python -m pip install -r requirements.txt
```

For a macOS TA-Lib build error, install the native library with `brew install ta-lib` and retry installation.

Set the API key locally:

```bash
export DEEPSEEK_API_KEY='YOUR_KEY'
```

Alternatively, copy `.env.example` to `.env` and fill in the key. The populated `.env` file is ignored by Git. No key is needed to evaluate saved outputs.

## Evaluate Saved Results

This command uses only the Python standard library and makes no API requests:

```bash
python3 experiments/evaluate.py
```

It verifies upstream checksums and writes `results/directional_scores.csv` and `results/evaluation_summary.json`.

## Run the Experiments

These commands make paid DeepSeek API calls. Use the same model for both settings. Model: `deepseek-flash`; endpoint: `https://api.deepseek.com`; temperature: 0.1; thinking: disabled; top-p and output-token limit: unspecified. Agent prompts, tools, graph, and author retry logic remain unchanged.

Baseline, three runs:

```bash
python experiments/run_btc100.py --timeframe 4h --window 97 --run 1
python experiments/run_btc100.py --timeframe 4h --window 97 --run 2
python experiments/run_btc100.py --timeframe 4h --window 97 --run 3
```

Modified window, three runs:

```bash
python experiments/run_btc100.py --timeframe 4h --window 50 --run 1
python experiments/run_btc100.py --timeframe 4h --window 50 --run 2
python experiments/run_btc100.py --timeframe 4h --window 50 --run 3
```

Each command processes 100 segments. Results are saved under `experiments/btc4h_original_runN/` or `experiments/btc4h_window50_runN/`. Repeating the command skips completed samples and retries failed samples. To score a new batch, copy its completed JSON files into the corresponding `results/` folder and run the evaluator.

## Design and Metric

Each segment contains 100 candles. The baseline observes candles 1–97; the modified condition observes candles 48–97. Candles 98–100 are withheld in both conditions. The forecast origin and targets are unchanged.

For a LONG decision, each target close above candle 97's close counts as one hit; for SHORT, each target close below it counts as one hit. Accuracy is total hits divided by 300. Ties do not count as hits. Standard deviation and variance use the sample formula across three runs.

## Results

| History | Run 1 | Run 2 | Run 3 | Mean | SD (pp) | Variance (pp²) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 97 candles | 46.00% | 45.00% | 41.00% | 44.00% | 2.65 | 7.00 |
| 50 candles | 44.67% | 42.00% | 44.00% | 43.56% | 1.39 | 1.93 |

The paper reports 50.7% for BTC 4h. The reproduced baseline mean is 6.7 percentage points lower. The underlying LLM differs, so these results are not directly comparable to the paper's model configuration. Reducing history to 50 candles changes mean accuracy by −0.44 percentage points.

## Debug Notes

- Python 3.9 was replaced with a separate Python 3.12 environment to satisfy dependencies.
- DeepSeek's default thinking mode produced HTTP 400 errors requiring `reasoning_content` in subsequent requests. Thinking was explicitly disabled in the external adapter.
- Network interruptions caused connection and timeout failures. The batch launcher preserves completed outputs and allows failed samples to be retried.
- The author pattern-agent flow can return a fallback when no chart tool is called. That behavior was retained.

## Reference

Xiong, F., Zhang, X., Feng, A., Sun, S., & You, C. (2025). Quantagent: Price-driven multi-agent llms for high-frequency trading. *arXiv preprint arXiv:2509.09995*.
