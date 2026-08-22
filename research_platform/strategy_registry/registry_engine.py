"""Registry engine verifying strategy inputs and instantiating registrations.
"""

from __future__ import annotations

from typing import List
from research_platform.strategy_registry.models import RegisteredStrategy


class RegistryEngine:
    """Verifies author details, git commits format, and registers strategy cards."""

    def create_registration(
        self,
        strategy_id: str,
        name: str,
        description: str,
        version: str,
        git_hash: str,
        dependencies: List[str],
        tags: List[str],
        categories: List[str],
        author: str,
        asset_class: str,
        risk_profile: str,
        capabilities: List[str]
    ) -> RegisteredStrategy:
        if not strategy_id or not name:
            raise ValueError("Strategy ID and Name must not be blank.")
        if not git_hash or len(git_hash) < 7:
            raise ValueError("Invalid Git Commit Hash: Git hash must be at least 7 characters.")
        if risk_profile not in ["LOW", "MEDIUM", "HIGH"]:
            raise ValueError("Invalid Risk Profile: Profile must be LOW, MEDIUM, or HIGH.")

        return RegisteredStrategy(
            strategy_id=strategy_id,
            name=name,
            description=description,
            active_version=version,
            git_hash=git_hash,
            dependencies=dependencies,
            tags=tags,
            categories=categories,
            author=author,
            asset_class=asset_class,
            risk_profile=risk_profile,
            runtime_capabilities=capabilities
        )
