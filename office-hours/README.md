# office-hours/

Workspace for the **"Should I Be Trading?"** dashboard feature. See [`SPEC.md`](./SPEC.md) for the full methodology.

This is isolated from `server/` and `web/` so we can iterate freely. Adapters and scoring engine here will be promoted into `server/app/services/` once the signal set and thresholds are validated on historical data.

## Layout

```
office-hours/
├── SPEC.md                 methodology: inputs, weights, kill-switches, decision logic
├── adapters/               data source clients (httpx, testable)
│   ├── fred.py             credit/liquidity bucket (HY OAS, IG OAS, net liquidity, SOFR)
│   ├── yahoo.py            vol term structure + cross-asset (^VIX, ^VIX3M, ^VVIX, ^MOVE, ...)
│   └── breadth.py          McClellan, net new H-L, AD line, equity P/C (via Yahoo)
├── scoring/                pure-function scoring engine
│   ├── normalize.py        rolling z-score, bucket-score mapping, percentile rank
│   ├── composite.py        bucket weights + weighted sum
│   └── decision.py         YES/CAUTION/NO + kill-switches + calendar downgrade
├── pipeline.py             adapters -> signals -> bucket scores -> decision
├── api.py                  FastAPI router exposing /should-i-trade
├── tests/                  pytest + httpx.MockTransport + FastAPI TestClient, no network
└── README.md
```

## Running the service locally

```bash
pip install fastapi httpx pandas numpy pytest pytest-asyncio
export FRED_API_KEY=your_free_key_from_stlouisfed_org

cd office-hours
PYTHONPATH=. uvicorn api:app --port 8001 --reload
curl http://localhost:8001/should-i-trade | jq
curl http://localhost:8001/should-i-trade/health | jq
```

Without a FRED key the live endpoint returns a structured 503; `/health`
still responds and reports `fred_configured: false`.

## Running tests

The scoring engine and adapters use only `pandas`, `numpy`, and `httpx` — already in `server/pyproject.toml`. From the repo root:

```bash
python3 -m pytest office-hours/tests -v
```

`tests/conftest.py` puts `office-hours/` on `sys.path`, so tests import the subpackages directly (`from scoring import ...`, `from adapters.fred import ...`). The hyphenated folder is not itself a Python package — that's intentional; the subpackages are.

Expected: 32 tests pass in ~3s.

## What this does NOT have yet

Intentionally deferred to keep each iteration focused:

- `% stocks above 50d MA` (`$SPXA50R`) — no clean free API; defer to a
  constituent-loop via the existing Polygon client when we move into `server/`.
- Dealer GEX adapter — SpotGamma/menthorq free chart scrape vs paid tier.
- CFTC COT adapter.
- NAAIM weekly adapter.
- Execution Window Score implementation.
- Persistent history store needed to percentile-map the composite (right now `market_quality_score` is the raw composite; the percentile map is ready in `scoring.normalize.percentile_rank` but needs a rolling composite series).
- Frontend panel in `web/` (needs a charting lib decision: Recharts vs Lightweight Charts).

Each of these becomes its own focused iteration.

## Integration checklist (future)

1. Validate thresholds via historical replay on 3y of data (HY OAS 30 bps / 5d, VIX3M/VIX 0.95, SOFR-OIS 25 bps).
2. Walk-forward calibrate on rolling 5y windows.
3. Move `adapters/` into `server/app/services/data/` and register via the orchestrator.
4. Add Redis caching (`server/` already has Redis).
5. Feed `NRTAgent` regime probability as an additional input to the Trend bucket.
6. Ship the frontend panel.
