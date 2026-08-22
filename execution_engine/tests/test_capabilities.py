import pytest
from execution_engine.brokers.paper_broker import PaperBroker
from execution_engine.brokers.binance_broker import BinanceBroker
from execution_engine.brokers.capabilities import BrokerCapabilities


def test_paper_broker_capabilities():
    broker = PaperBroker({"initial_balance": 10000.0})
    caps = broker.get_capabilities()
    
    assert isinstance(caps, BrokerCapabilities)
    assert caps.supports_market is True
    assert caps.supports_limit is True
    assert caps.supports_oco is True
    assert caps.max_leverage == 20.0


def test_binance_broker_capabilities():
    broker = BinanceBroker({})
    caps = broker.get_capabilities()
    
    assert isinstance(caps, BrokerCapabilities)
    assert caps.supports_market is True
    assert caps.supports_brackets is False
    assert caps.max_leverage == 125.0
