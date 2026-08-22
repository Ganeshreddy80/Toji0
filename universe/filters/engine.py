"""Configurable asset filter chain engine.

Applies a sequence of filter rules to the universe,
rejecting assets that don't meet institutional quality thresholds.
Supports blacklists, whitelists, and arbitrary field comparisons.
"""

from __future__ import annotations

import logging
from typing import Any

from universe.core.interfaces import IAssetFilter
from universe.core.models import (
    FilterOperator,
    FilterResult,
    FilterRule,
    UniverseAsset,
    UniverseConfig,
)

logger = logging.getLogger(__name__)


class FilterEngine(IAssetFilter):
    """Configurable rule chain for filtering universe assets.

    Built-in filter rules are constructed from UniverseConfig defaults.
    Additional custom rules can be passed via constructor.
    Whitelisted symbols bypass all rejection rules.
    """

    def __init__(
        self,
        config: UniverseConfig | None = None,
        custom_rules: list[FilterRule] | None = None,
    ) -> None:
        self._config = config or UniverseConfig()
        self._rules = custom_rules or self._build_default_rules()

    def apply(
        self, assets: list[UniverseAsset]
    ) -> tuple[list[UniverseAsset], list[FilterResult]]:
        """Run all filter rules against the asset list.

        Returns:
            (passed_assets, all_filter_results)
        """
        all_results: list[FilterResult] = []
        passed: list[UniverseAsset] = []
        whitelist = set(self._config.whitelisted_symbols)
        blacklist = set(self._config.blacklisted_symbols)

        for asset in assets:
            # Blacklist always rejects
            if asset.symbol in blacklist or asset.base_asset in blacklist:
                all_results.append(
                    FilterResult(
                        symbol=asset.symbol,
                        rule_name="blacklist",
                        passed=False,
                        reason=f"{asset.symbol} is blacklisted",
                    )
                )
                continue

            # Whitelist overrides all other rules
            if asset.symbol in whitelist or asset.base_asset in whitelist:
                all_results.append(
                    FilterResult(
                        symbol=asset.symbol,
                        rule_name="whitelist_override",
                        passed=True,
                        reason="Whitelisted — bypasses all filters",
                    )
                )
                passed.append(asset)
                continue

            # Apply each rule
            asset_passed = True
            for rule in self._rules:
                if not rule.enabled:
                    continue

                result = self._evaluate_rule(asset, rule)
                all_results.append(result)
                if not result.passed:
                    asset_passed = False
                    break  # Short-circuit: first failure rejects

            if asset_passed:
                passed.append(asset)

        logger.info(
            "Filter: %d/%d assets passed (%d rejected)",
            len(passed),
            len(assets),
            len(assets) - len(passed),
        )
        return passed, all_results

    def _evaluate_rule(
        self, asset: UniverseAsset, rule: FilterRule
    ) -> FilterResult:
        """Evaluate a single filter rule against an asset."""
        try:
            value = getattr(asset, rule.field, None)
        except AttributeError:
            return FilterResult(
                symbol=asset.symbol,
                rule_name=rule.name,
                passed=True,
                reason=f"Field '{rule.field}' not found, skipping",
            )

        if value is None:
            # Cannot evaluate — pass by default (don't penalize missing data)
            return FilterResult(
                symbol=asset.symbol,
                rule_name=rule.name,
                passed=True,
                reason=f"Field '{rule.field}' is None, passing by default",
            )

        passed = self._compare(value, rule.operator, rule.threshold)
        reason = "" if passed else (
            f"{rule.name}: {rule.field}={value} failed "
            f"{rule.operator.value} {rule.threshold}"
        )

        return FilterResult(
            symbol=asset.symbol,
            rule_name=rule.name,
            passed=passed,
            reason=reason,
        )

    def _compare(
        self,
        value: Any,
        operator: FilterOperator,
        threshold: float | str | list[str],
    ) -> bool:
        """Perform the comparison operation."""
        if operator == FilterOperator.GT:
            return float(value) > float(threshold)
        if operator == FilterOperator.GTE:
            return float(value) >= float(threshold)
        if operator == FilterOperator.LT:
            return float(value) < float(threshold)
        if operator == FilterOperator.LTE:
            return float(value) <= float(threshold)
        if operator == FilterOperator.EQ:
            return value == threshold
        if operator == FilterOperator.NEQ:
            return value != threshold
        if operator == FilterOperator.IN:
            return str(value) in (threshold if isinstance(threshold, list) else [str(threshold)])
        if operator == FilterOperator.NOT_IN:
            return str(value) not in (threshold if isinstance(threshold, list) else [str(threshold)])
        return True

    def _build_default_rules(self) -> list[FilterRule]:
        """Construct default filter rules from config."""
        rules: list[FilterRule] = []

        # Minimum 24h volume
        rules.append(
            FilterRule(
                name="min_volume",
                field="volume_24h_usd",
                operator=FilterOperator.GTE,
                threshold=self._config.min_volume_24h_usd,
            )
        )

        # Minimum price
        rules.append(
            FilterRule(
                name="min_price",
                field="price_usd",
                operator=FilterOperator.GTE,
                threshold=self._config.min_price_usd,
            )
        )

        # Quote asset filter
        rules.append(
            FilterRule(
                name="quote_asset",
                field="quote_asset",
                operator=FilterOperator.IN,
                threshold=self._config.allowed_quote_assets,
            )
        )

        return rules
