"""Workspace module for organizing and persisting quantitative research projects.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ResearchProjectMetadata:
    """Metadata detailing a research project."""
    name: str
    description: str
    created_at: str
    authors: List[str] = field(default_factory=list)
    strategies: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class ResearchWorkspace:
    """Manages filesystems, structures, and metadata for a research project."""

    def __init__(self, workspace_root: str | Path) -> None:
        self.root = Path(workspace_root)
        self.datasets_dir = self.root / "datasets"
        self.experiments_dir = self.root / "experiments"
        self.strategies_dir = self.root / "strategies"
        self.metadata_file = self.root / "project.json"

    def initialize_workspace(
        self,
        name: str,
        description: str,
        authors: Optional[List[str]] = None
    ) -> ResearchProjectMetadata:
        """Create workspace directories and seed the project metadata file."""
        self.datasets_dir.mkdir(parents=True, exist_ok=True)
        self.experiments_dir.mkdir(parents=True, exist_ok=True)
        self.strategies_dir.mkdir(parents=True, exist_ok=True)

        from datetime import datetime, timezone
        created_at_str = datetime.now(timezone.utc).isoformat()

        meta = ResearchProjectMetadata(
            name=name,
            description=description,
            created_at=created_at_str,
            authors=authors or [],
            strategies={}
        )
        self.save_metadata(meta)
        return meta

    def save_metadata(self, metadata: ResearchProjectMetadata) -> None:
        """Save workspace metadata JSON."""
        with open(self.metadata_file, "w") as f:
            json.dump(asdict(metadata), f, indent=4)

    def load_metadata(self) -> ResearchProjectMetadata:
        """Load workspace metadata JSON."""
        if not self.metadata_file.exists():
            raise FileNotFoundError(f"Project metadata not found at {self.metadata_file}")
        with open(self.metadata_file, "r") as f:
            data = json.load(f)
        return ResearchProjectMetadata(
            name=data["name"],
            description=data["description"],
            created_at=data["created_at"],
            authors=data.get("authors", []),
            strategies=data.get("strategies", {})
        )

    def register_strategy(self, strategy_id: str, code_path: str, parameters: Dict[str, Any]) -> None:
        """Register a strategy version inside the workspace metadata."""
        meta = self.load_metadata()
        meta.strategies[strategy_id] = {
            "code_path": str(code_path),
            "parameters": parameters,
            "registered_at": os.path.getmtime(code_path) if os.path.exists(code_path) else None
        }
        self.save_metadata(meta)
