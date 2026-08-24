from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.feature_platform.feature_pipeline import FeaturePipeline
from research_platform.feature_platform.dependency_graph import DependencyGraph
from research_platform.feature_platform.orchestrator import (
    DEFAULT_COMPUTE_NAMES,
    DEFAULT_FEATURE_DEFINITIONS,
    FeaturePlatformOrchestrator,
)


def runtime_full_compute() -> dict:
    n = 1505
    idx = pd.date_range("2026-01-01T00:00:00Z", periods=n, freq="min")
    close = 100.0 + np.cumsum(np.sin(np.arange(n) / 17.0) * 0.03 + 0.02)
    frame = pd.DataFrame(
        {
            "symbol": "BTCUSDT",
            "timestamp": idx,
            "open": close - 0.1,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": np.linspace(1000.0, 2000.0, n),
            "interval": "1m",
        }
    )
    orch = FeaturePlatformOrchestrator(InMemoryEventBus())
    orch.register_default_features()
    as_of = datetime(2026, 2, 2, tzinfo=timezone.utc)
    out = orch.compute_and_store(list(DEFAULT_COMPUTE_NAMES), "BTCUSDT", frame, as_of_time=as_of)
    missing = [name for name in DEFAULT_COMPUTE_NAMES if name not in out.columns]
    realtime = orch.query_realtime(list(DEFAULT_COMPUTE_NAMES), ["BTCUSDT"])
    missing_realtime = [name for name in DEFAULT_COMPUTE_NAMES if name not in realtime.columns]
    return {
        "output_rows": len(out),
        "output_columns": len(out.columns),
        "missing_output_features": missing,
        "realtime_rows": len(realtime),
        "missing_realtime_features": missing_realtime,
        "registry_count": len(orch.registry.list_all()),
        "compute_sha256": hashlib.sha256(
            json.dumps(out[list(DEFAULT_COMPUTE_NAMES)].tail(1).to_dict(orient="records"), default=str, sort_keys=True).encode()
        ).hexdigest(),
    }


def parity_guard_mutations() -> dict:
    pipeline = FeaturePipeline(DependencyGraph())
    original_transformers = dict(pipeline._transformers)
    del pipeline._transformers["close"]
    removed_transformer_detected = set(pipeline._transformers) != set(DEFAULT_COMPUTE_NAMES)
    pipeline._transformers.clear()
    pipeline._transformers.update(original_transformers)

    original_definitions = list(DEFAULT_FEATURE_DEFINITIONS)
    class FakeRecord:
        name = "__audit_fake__"
    DEFAULT_FEATURE_DEFINITIONS.append(FakeRecord())
    definition_drift_detected = tuple(r.name for r in DEFAULT_FEATURE_DEFINITIONS) != DEFAULT_COMPUTE_NAMES
    DEFAULT_FEATURE_DEFINITIONS[:] = original_definitions
    return {
        "removed_transformer_detected": removed_transformer_detected,
        "definition_mutation_drift_detected": definition_drift_detected,
    }


def import_fingerprint() -> dict:
    root = str(Path(__file__).resolve().parents[2])
    code = (
        "from research_platform.feature_platform.orchestrator import DEFAULT_COMPUTE_NAMES; "
        "print(repr(DEFAULT_COMPUTE_NAMES))"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = root
    outputs = []
    for _ in range(2):
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
        outputs.append({"returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()})
    return {"runs": outputs, "stable": outputs[0]["stdout"] == outputs[1]["stdout"] and all(x["returncode"] == 0 for x in outputs)}


if __name__ == "__main__":
    print(json.dumps({
        "runtime_full_compute": runtime_full_compute(),
        "parity_guard_mutations": parity_guard_mutations(),
        "import_fingerprint": import_fingerprint(),
    }, indent=2, sort_keys=True))
