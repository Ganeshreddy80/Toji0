from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.feature_platform.orchestrator import DEFAULT_COMPUTE_NAMES, FeaturePlatformOrchestrator


def make_frame(n: int) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01T00:00:00Z", periods=n, freq="min")
    close = 100.0 + np.cumsum(0.01 + np.sin(np.arange(n) / 17.0) * 0.03)
    return pd.DataFrame({
        "symbol": "BTCUSDT", "timestamp": idx,
        "open": close - 0.1, "high": close + 0.2, "low": close - 0.2,
        "close": close, "volume": np.linspace(1000.0, 2000.0, n), "interval": "1m",
    })


def probe(n: int) -> dict:
    orch = FeaturePlatformOrchestrator(InMemoryEventBus())
    orch.register_default_features()
    out = orch.compute_and_store(list(DEFAULT_COMPUTE_NAMES), "BTCUSDT", make_frame(n), as_of_time=datetime(2026, 2, 2, tzinfo=timezone.utc))
    realtime = orch.query_realtime(list(DEFAULT_COMPUTE_NAMES), ["BTCUSDT"])
    return {
        "input_rows": n,
        "computed_features": [name for name in DEFAULT_COMPUTE_NAMES if name in out.columns],
        "persisted_features": [name for name in DEFAULT_COMPUTE_NAMES if name in realtime.columns],
        "missing_persisted_features": [name for name in DEFAULT_COMPUTE_NAMES if name not in realtime.columns],
        "annualized_vol_nan_ratio": float(out["annualized_vol"].isna().mean()),
    }


if __name__ == "__main__":
    print(json.dumps({"probes": [probe(1505), probe(9000)]}, indent=2))
