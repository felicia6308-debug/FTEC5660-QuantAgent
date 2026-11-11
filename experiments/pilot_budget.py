"""Run one BTC 1h window; keep original agent flow and log usage, never keys."""
import json
import argparse
import os
import time
import sys
import httpx
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent / "QuantHarness-main"
sys.path.insert(0, str(ROOT))
from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI
from trading_graph import TradingGraph
import pandas as pd

for path in [ROOT / 'tests' / '.env', ROOT.parent / '.env', ROOT / '.env']:
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip().startswith('DEEPSEEK_API_KEY='):
                os.environ.setdefault('DEEPSEEK_API_KEY', line.split('=', 1)[1].strip().strip('\"\''))
key = os.environ.get('DEEPSEEK_API_KEY')
if not key:
    raise SystemExit('Set DEEPSEEK_API_KEY in environment or .env first.')

REQUEST_LOG = []
def inspect_request(request):
    if request.method == 'POST':
        payload = json.loads(request.content)
        REQUEST_LOG.append({
            'model': payload.get('model'),
            'max_tokens': payload.get('max_tokens'),
            'max_completion_tokens': payload.get('max_completion_tokens'),
            'thinking': payload.get('thinking'),
            'tools': [t['function']['name'] for t in payload.get('tools', [])],
            'image_parts': sum(1 for m in payload.get('messages', [])
                               if isinstance(m.get('content'), list)
                               for part in m['content'] if part.get('type') == 'image_url'),
        })

class Usage(BaseCallbackHandler):
    def __init__(self):
        self.calls = []
    def on_llm_end(self, response, **kwargs):
        usage = (response.llm_output or {}).get('token_usage', {})
        self.calls.append(usage)
        if REQUEST_LOG:
            REQUEST_LOG[-1]['finish_reasons'] = [g.generation_info for batch in response.generations for g in batch]
            REQUEST_LOG[-1]['tool_calls_returned'] = [[t.get('name') for t in getattr(g.message, 'tool_calls', [])] for batch in response.generations for g in batch]

class DeepSeekChat(ChatOpenAI):
    def _get_request_payload(self, *args, **kwargs):
        payload = super()._get_request_payload(*args, **kwargs)
        if 'max_completion_tokens' in payload:
            payload['max_tokens'] = payload.pop('max_completion_tokens')
        return payload

class DeepSeekGraph(TradingGraph):
    def _create_llm(self, provider, model, temperature):
        return DeepSeekChat(model='deepseek-flash', api_key=key,
                          base_url='https://api.deepseek.com', temperature=temperature,
                          max_retries=0, timeout=120,
                          http_client=httpx.Client(event_hooks={'request': [inspect_request]}),
                          extra_body={'thinking': {'type': 'disabled'}})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--window', type=int, choices=[50,97], default=97)
    parser.add_argument('--timeframe', choices=['1h','4h'], default='1h')
    parser.add_argument('--sample', type=int, default=1, choices=range(1,101))
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parent / 'pilot_results')
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(exist_ok=True)
    data_dir = ROOT / ('benchmark/1h/btc' if args.timeframe == '1h' else 'benchmark/btc')
    source = data_dir / f'BTC_{args.timeframe}_{args.sample}.csv'
    df = pd.read_csv(source)
    observed = df.iloc[:-3].tail(args.window).copy()
    usage = Usage()
    start = time.monotonic()
    result = {}
    try:
        graph = DeepSeekGraph()
        state = graph.graph.invoke({'kline_data': observed.to_dict(orient='list'),
                                    'time_frame': ('1hour' if args.timeframe == '1h' else '4hour'), 'stock_name': 'BTC',
                                    'messages': [], 'analysis_results': ''},
                                   config={'callbacks': [usage], 'recursion_limit': 30})
        result['reports'] = {k: state.get(k) for k in ['indicator_report', 'pattern_report', 'trend_report', 'final_trade_decision']}
        result['status'] = 'completed'
    except Exception as exc:
        result['status'] = 'failed'
        result['error_type'] = type(exc).__name__
        # Avoid serializing raw HTTP exceptions, which can contain sensitive payloads.
    result.update(source=str(source.relative_to(ROOT)), input_rows=len(observed),
                  withheld_rows=3, history_window=args.window, model='deepseek-flash', thinking='disabled',
                  max_output_tokens_per_call=None, execution_mode='original_agent_flow', seconds=time.monotonic()-start,
                  usage_per_call=usage.calls, request_diagnostics=REQUEST_LOG)
    (output / f'BTC_{args.timeframe}_{args.sample}_original_flow_nonthinking.json').write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps({k:v for k,v in result.items() if k != 'reports'}, indent=2))
