import pandas as pd

from app.services.auditor import DecisionAuditor


def _market(implied_vol: float, closes: list[float]) -> dict:
    idx = pd.date_range("2024-01-02 14:40:00+00:00", periods=len(closes), freq="5T", tz="UTC")
    bars = pd.DataFrame(
        {
            "open": closes,
            "high": [c + 0.5 for c in closes],
            "low": [c - 0.5 for c in closes],
            "close": closes,
            "volume": [100_000] * len(closes),
        },
        index=idx,
    )
    return {
        "bars_5m": bars,
        "options_snapshot": {"implied_volatility": implied_vol, "depth_ok": True},
    }


def test_auditor_flags_large_implied_move():
    auditor = DecisionAuditor(implied_sigma_limit=1.5)
    market = _market(implied_vol=2.0, closes=[100.0] * 200)
    overall = {"decision": "BUY", "confidence": 0.8, "method": "weighted"}
    results = {
        "technical": {
            "decision": "BUY",
            "confidence": 0.8,
            "inputs": {"example": 1},
            "notes": "stub",
        }
    }

    updated = auditor.verify(market, results, overall)

    assert updated["decision"] == "NO_TRADE"
    assert updated["method"] == "auditor_override"
    assert "failure_modes" in updated["auditor_notes"]
    assert "implied_move_outlier" in updated["auditor_notes"]["failure_modes"]


def test_auditor_passes_clean_data():
    auditor = DecisionAuditor()
    closes = [100 + i * 0.1 for i in range(200)]
    market = _market(implied_vol=0.5, closes=closes)
    overall = {"decision": "BUY", "confidence": 0.6, "method": "weighted"}
    results = {
        "technical": {
            "decision": "BUY",
            "confidence": 0.6,
            "inputs": {"example": 1},
            "notes": "stub",
        }
    }

    updated = auditor.verify(market, results, overall)

    assert updated["decision"] == "BUY"
    assert updated["method"] == "weighted"
    assert "realized_vol_5d" in updated.get("auditor_notes", {})
