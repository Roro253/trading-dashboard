# office-hours/

Workspace for the **"Should I Be Trading?"** dashboard feature. See [`SPEC.md`](./SPEC.md) for the full methodology.

This is isolated from `server/` and `web/` so we can iterate freely. Adapters and scoring engine here will be promoted into `server/app/services/` once the signal set and thresholds are validated on historical data.

## Layout

```
office-hours/
├── SPEC.md                 methodology: inputs, weights, kill-switches, decision logic
├── adapters/               data source clients (httpx, testable)
│   ├── fred.py             credit/liquidity bucket (HY OAS, IG OAS, net liquidity, SOFR)
│   └── yahoo.py            vol term structure + cross-asset (^VIX, ^VIX3M, ^VVIX, ^MOVE, ...)
├── scoring/                pure-function scoring engine
│   ├── normalize.py        rolling z-score, bucket-score mapping, percentile rank
│   ├── composite.py        bucket weights + weighted sum
│   └── decision.py         YES/CAUTION/NO + kill-switches + calendar downgrade
├── tests/                  pytest + httpx.MockTransport — no network
└── README.md
```

## Running tests

The scoring engine and adapters use only `pandas`, `numpy`, and `httpx` — already in `server/pyproject.toml`. From the repo root:

```bash
python3 -m pytest office-hours/tests -v
```

`tests/conftest.py` puts `office-hours/` on `sys.path`, so tests import the subpackages directly (`from scoring import ...`, `from adapters.fred import ...`). The hyphenated folder is not itself a Python package — that's intentional; the subpackages are.

Expected: 22 tests pass in ~1s.

## What this does NOT have yet

Intentionally deferred to keep this PR focused:

- Breadth adapter (StockCharts / `$NYMO`, `$NYSI`, `$CPCE`, `$SPXA50R`) — no clean free API, need to decide on scrape vs paid
- Dealer GEX adapter — SpotGamma/menthorq free chart scrape vs paid tier
- CFTC COT adapter
- NAAIM weekly adapter
- Execution Window Score implementation
- FastAPI router (`api.py`) that assembles everything and serves `/api/should-i-trade`
- Frontend panel in `web/` (needs a charting lib decision: Recharts vs Lightweight Charts)

Each of these becomes its own focused iteration once the foundation here is reviewed.

## Integration checklist (future)

1. Validate thresholds via historical replay on 3y of data (HY OAS 30 bps / 5d, VIX3M/VIX 0.95, SOFR-OIS 25 bps).
2. Walk-forward calibrate on rolling 5y windows.
3. Move `adapters/` into `server/app/services/data/` and register via the orchestrator.
4. Add Redis caching (`server/` already has Redis).
5. Feed `NRTAgent` regime probability as an additional input to the Trend bucket.
6. Ship the frontend panel.
