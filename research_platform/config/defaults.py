"""R51 Configuration defaults mapping profiles.
"""

from __future__ import annotations

from typing import Dict, Any


DEFAULT_DEV_PROFILE: Dict[str, Any] = {
    "version": 1,
    "database": {
        "host": "localhost",
        "port": 5432,
        "username": "postgres",
        "password": "dev-password",
        "database": "toji_dev"
    },
    "exchange": {
        "base_url": "http://localhost:8081",
        "spread_pct": 0.02
    },
    "risk": {
        "max_order_size": 100.0,
        "max_position_size": 1000.0
    },
    "runtime": {
        "interval_sec": 0.1,
        "mode": "DEV"
    },
    "monitoring": {
        "latency_threshold_ms": 10.0
    },
    "reporting": {
        "enabled": False
    },
    "recovery": {
        "checkpoint_interval_sec": 5.0
    }
}

DEFAULT_PAPER_PROFILE: Dict[str, Any] = {
    "version": 1,
    "database": {
        "host": "toji-postgres",
        "port": 5432,
        "username": "toji_paper",
        "password": "paper-password",
        "database": "toji_paper"
    },
    "exchange": {
        "base_url": "https://api.paper.broker.local",
        "spread_pct": 0.01
    },
    "risk": {
        "max_order_size": 1000.0,
        "max_position_size": 5000.0
    },
    "runtime": {
        "interval_sec": 1.0,
        "mode": "PAPER"
    },
    "monitoring": {
        "latency_threshold_ms": 50.0
    },
    "reporting": {
        "enabled": True,
        "frequency_minutes": 15
    },
    "recovery": {
        "checkpoint_interval_sec": 10.0
    }
}

DEFAULT_PROD_PROFILE: Dict[str, Any] = {
    "version": 1,
    "database": {
        "host": "toji-postgres",
        "port": 5432,
        "username": "toji_prod",
        "password": "prod-password",
        "database": "toji_prod"
    },
    "exchange": {
        "base_url": "https://api.exchange.prod",
        "spread_pct": 0.005
    },
    "risk": {
        "max_order_size": 5000.0,
        "max_position_size": 25000.0
    },
    "runtime": {
        "interval_sec": 0.5,
        "mode": "PROD"
    },
    "monitoring": {
        "latency_threshold_ms": 20.0
    },
    "reporting": {
        "enabled": True,
        "frequency_minutes": 60
    },
    "recovery": {
        "checkpoint_interval_sec": 30.0
    }
}
