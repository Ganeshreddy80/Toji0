import pytest

from execution_engine.brokers.broker_router import BrokerRouter
from execution_engine.brokers.paper_broker import PaperBroker
from execution_engine.core.exceptions import BrokerError


def test_broker_router_resolution():
    router = BrokerRouter()
    
    # Missing resolution should fail
    with pytest.raises(BrokerError):
        router.get_adapter("binance")
        
    paper = PaperBroker({})
    router.register_adapter("paper", paper)
    
    assert router.get_adapter("paper") is paper
    assert router.get_adapter("PAPER") is paper  # Case insensitive check
