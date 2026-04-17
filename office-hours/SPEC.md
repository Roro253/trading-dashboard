# Should I Be Trading? — Dashboard Spec

## Context

The base prompt from X describes a retail "risk-on/off" dashboard (VIX + SPY vs MA + sector ETFs + 10Y/DXY + FOMC flag). It's a reasonable starting point but misses the layers that materially separate professional risk desks from retail tools:

1. **Credit spreads** (HY OAS) — lead equity at most major inflection points
2. **Vol term structure** (VIX3M/VIX ratio) — backwardation is a far better stress signal than spot VIX level
3. **Dealer positioning** (GEX, zero-gamma) — dictates whether intraday regime is pinning or trending
4. **Fed net liquidity** — quantitative replacement for the qualitative "Fed stance" label
5. **Z-score normalization + walk-forward calibration** — fixes the hidden flaw where raw-value fixed-weight sums let the largest-range indicator dominate

This spec replaces the base prompt's retail framework with one those three fixes actually deliver edge.

This also addresses an existing repo bug: `server/` currently proxies VIX from SPY rolling stddev, not the real VIX. Real term-structure feeds fix that as a side effect.

---

## Outputs

The dashboard emits three things on every refresh:

1. **Decision**: `YES` / `CAUTION` / `NO` (with reason code when kill-switch fires)
2. **Market Quality Score**: 0–100 (percentile of composite over trailing 3y)
3. **Execution Window Score**: 0–100 (separate — gates sizing within a given decision)
4. **Plain-English Summary**: short LLM-generated narrative

---

## Data inputs

### Credit / Liquidity (25%)

| Signal | Source | Freshness |
|---|---|---|
| HY OAS level + 1w Δ (ICE BofA) | FRED `BAMLH0A0HYM2` | Daily |
| IG OAS level | FRED `BAMLC0A0CM` | Daily |
| MOVE index | Yahoo `^MOVE` | Daily |
| Fed Net Liquidity = WALCL − TGA − RRP, 4w Δ | FRED `WALCL`, `WTREGEN`, `RRPONTSYD` | Weekly (Wed) |
| SOFR-OIS spread (kill-switch) | FRED `SOFR` + OIS proxy | Daily |

### Volatility term structure (20%)

| Signal | Source |
|---|---|
| VIX3M / VIX ratio | Yahoo `^VIX`, `^VIX3M` |
| VIX9D / VIX ratio | Yahoo `^VIX9D`, `^VIX` |
| VVIX percentile (1y) | Yahoo `^VVIX` |
| VRP = VIX − HV20(SPY, annualized) | computed |
| SKEW gate | Yahoo `^SKEW` |

### Trend (15%)

- SPX vs 50d/200d MA, 50>200 state
- Slope of 50d MA
- NO RSI14 — redundant with MA stack

### Breadth (15%)

- McClellan Oscillator (`$NYMO`), Summation Index (`$NYSI`)
- % stocks above 50d MA (`$SPXA50R`)
- Net new 52w H − L (`$NYHL`)
- AD line divergence flag (cumulative `$NYAD` vs SPX)

### Dealer positioning (10%)

- GEX sign + zero-gamma distance (SpotGamma free chart / menthorq free tier)
- Equity-only P/C 5d avg (`$CPCE`) — **not** index P/C

### Positioning / sentiment (8%)

- NAAIM Exposure Index z-score (1y)
- AAII bull-bear spread
- CFTC COT net non-commercial z-score (S&P e-mini)

### Cross-asset (5%)

- HYG/LQD ratio 20d trend
- Copper/gold ratio 20d trend
- USDJPY shock flag (>1.5σ 1d move)

### Calendar / structural (2%)

- FOMC / CPI / NFP 24-hour flag (half-size gate)
- OPEX week flag

---

## Scoring methodology

**This is the part the base prompt gets wrong.**

### Step 1 — Normalize each input
Z-score every raw signal on a **rolling 3-year window**. Clamp to ±3. This prevents the largest-numerical-range input from dominating the composite.

### Step 2 — Map to 0–100 per bucket
Translate z-score to bucket-score via:
```
bucket_score = 50 + 16.67 * clamp(z, -3, 3)
```
(yields 0–100 with z=0 → 50, |z|=3 → 0 or 100)

Weight components within a bucket by inverse-volatility of the signal itself (noisier signals get less weight), not by subjective importance.

### Step 3 — Composite
Weighted sum across buckets with the professional allocation:

| Bucket | Weight |
|---|---|
| Credit/Liquidity | 25% |
| Vol term structure | 20% |
| Trend | 15% |
| Breadth | 15% |
| Dealer positioning | 10% |
| Positioning/sentiment | 8% |
| Cross-asset | 5% |
| Calendar | 2% |

### Step 4 — Percentile map
Map the composite to its **3-year trailing percentile** to get the final 0–100 Market Quality Score. This makes "80" mean "top 20% of the last 3 years" not "summed to 80 on arbitrary scales."

### Step 5 — Decision
- `>= 80` → **YES** (full size)
- `60–79` → **CAUTION** (half size, A+ setups only)
- `< 60` → **NO** (preserve capital)

### Step 6 — Kill-switch overrides (bypass score → force NO)
- HY OAS widens **> 30 bps in 5 days**
- **VIX3M / VIX < 0.95** (backwardation)
- **SOFR-OIS > 25 bps** (funding stress)

Each kill-switch emits a reason code in the output.

### Step 7 — Calendar half-size
If within 24h of FOMC / CPI / NFP print and decision is YES → downgrade to CAUTION.

---

## Execution Window Score (separate)

Gates *how* you trade within the decision above. Does not feed the main score.

| Input | Logic |
|---|---|
| IBD Follow-Through Day | Day 4+ of rally attempt, SPX +1.25% on higher vol → +30 |
| Distribution days | 5+ in rolling 4–5 weeks → −30 |
| SPY realized vs expected move | Midday inside expected move = pinning; breakout outside = expansion |
| Opening-range continuation | OR direction holding to close correlates ~65% in trend regime |

Range 0–100. Below 40 = mechanical setups failing, pull size even on a YES day.

---

## Architecture

```
office-hours/
├── SPEC.md                    this file
├── adapters/                  data sources (one module per provider)
│   ├── fred.py                HY OAS, IG OAS, WALCL, TGA, RRP, SOFR
│   ├── yahoo.py               ^VIX*, ^VVIX, ^MOVE, ^SKEW, ETFs
│   ├── stockcharts.py         breadth ($NYMO, $NYSI, $CPCE, etc.)
│   ├── naaim.py               weekly exposure index scrape
│   ├── cot.py                 CFTC weekly positioning
│   └── gex.py                 dealer gamma (SpotGamma / menthorq)
├── scoring/
│   ├── normalize.py           rolling z-score, percentile map
│   ├── composite.py           bucket weights, weighted sum
│   ├── decision.py            YES/CAUTION/NO + kill-switches
│   └── execution_window.py    separate execution score
├── tests/
└── api.py                     FastAPI router — integrated into server/ later
```

### Integration path

Phase 1 (now): build + test in `office-hours/` with file-based caches.
Phase 2: wire adapters into `server/app/services/` as additional data providers.
Phase 3: expose `/api/should-i-trade` endpoint consuming existing `NRTAgent` regime + new scoring engine.
Phase 4: new frontend panel in `web/` (needs charting lib — Recharts or Lightweight Charts).

---

## Verification

1. **Unit**: each adapter mockable, scoring engine deterministic on fixtures.
2. **Historical replay**: run the scoring engine on last 3 years; verify it flags known stress periods (Aug 2024 yen unwind, Oct 2023, Mar 2020) as `NO` or kill-switch.
3. **Live check**: pull today's values, confirm output is sane and matches an independent risk view (CNBC fear/greed, SpotGamma daily note).
4. **Walk-forward calibration**: thresholds (30 bps HY OAS, 25 bps SOFR-OIS, 0.95 VIX3M/VIX) re-estimated on rolling 5y windows before production.
