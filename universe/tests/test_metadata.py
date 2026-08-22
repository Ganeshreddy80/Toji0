"""Tests for the metadata enrichment engine."""

from __future__ import annotations

from toji_platform.core.types import AssetClass
from universe.core.models import ContractType, UniverseAsset
from universe.metadata.engine import MetadataEngine


def _make_asset(
    symbol: str = "BTC/USDT",
    base: str = "BTC",
    quote: str = "USDT",
    **kwargs,
) -> UniverseAsset:
    return UniverseAsset(symbol=symbol, base_asset=base, quote_asset=quote, **kwargs)


class TestMetadataEngine:
    """Test metadata enrichment logic."""

    def test_enrich_preserves_existing_fields(self) -> None:
        engine = MetadataEngine()
        asset = _make_asset(tick_size=0.01, lot_size=0.001)
        enriched = engine.enrich([asset])
        assert len(enriched) == 1
        assert enriched[0].tick_size == 0.01
        assert enriched[0].lot_size == 0.001

    def test_enrich_applies_supplementary_data(self) -> None:
        supp = {
            "BTC/USDT": {
                "tick_size": 0.05,
                "volume_24h_usd": 5_000_000.0,
            }
        }
        engine = MetadataEngine(supplementary_data=supp)
        asset = _make_asset()
        enriched = engine.enrich([asset])
        assert enriched[0].tick_size == 0.05
        assert enriched[0].volume_24h_usd == 5_000_000.0

    def test_enrich_infers_asset_class_crypto(self) -> None:
        engine = MetadataEngine()
        asset = _make_asset()
        enriched = engine.enrich([asset])
        assert enriched[0].asset_class == AssetClass.CRYPTO

    def test_enrich_infers_forex_from_fiat_pair(self) -> None:
        engine = MetadataEngine()
        asset = _make_asset(symbol="EUR/USD", base="EUR", quote="USD")
        enriched = engine.enrich([asset])
        assert enriched[0].asset_class == AssetClass.FOREX

    def test_enrich_infers_perpetual_contract_type(self) -> None:
        engine = MetadataEngine()
        asset = _make_asset(symbol="BTC/USDT-PERP", base="BTC", quote="USDT-PERP")
        enriched = engine.enrich([asset])
        assert enriched[0].contract_type == ContractType.PERPETUAL

    def test_enrich_default_fee_tier(self) -> None:
        engine = MetadataEngine()
        asset = _make_asset(exchanges=["Binance"])
        enriched = engine.enrich([asset])
        assert enriched[0].fee_tier == "standard"

    def test_enrich_updates_last_updated(self) -> None:
        engine = MetadataEngine()
        asset = _make_asset()
        enriched = engine.enrich([asset])
        assert enriched[0].last_updated is not None

    def test_enrich_empty_list(self) -> None:
        engine = MetadataEngine()
        assert engine.enrich([]) == []
