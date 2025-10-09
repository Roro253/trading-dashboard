from types import SimpleNamespace

from app.workers import evaluator


def test_classify_outcome_buy_paths():
    assert evaluator._classify_outcome("BUY", 0.01) == "hit"
    assert evaluator._classify_outcome("BUY", -0.01) == "miss"
    assert evaluator._classify_outcome("BUY", 0.0) == "flat"


def test_compute_metrics_returns_expected_fields():
    signals = [
        SimpleNamespace(outcome_return=0.02, outcome_label="hit"),
        SimpleNamespace(outcome_return=-0.01, outcome_label="miss"),
        SimpleNamespace(outcome_return=0.0, outcome_label="flat"),
    ]

    metrics = evaluator._compute_metrics(signals)

    assert set(metrics.keys()) == {
        "hit_rate",
        "avg_R",
        "sharpe",
        "profit_factor",
        "drawdown",
        "samples",
        "calibration_bins",
    }
    assert metrics["samples"] == 3
    assert metrics["calibration_bins"]["hit"] == 1
