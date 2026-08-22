"""TOJI OS orchestrator coordinating booting sequences, active workspace maps, and clean shutdowns.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.toji_os.models import OSSession, WorkspaceState
from research_platform.toji_os.repository import TOJIOSRepository
from research_platform.toji_os.kernel import OSKernel
from research_platform.toji_os.workspace_manager import WorkspaceManager
from research_platform.toji_os.module_registry import ModuleRegistry
from research_platform.toji_os.startup_manager import StartupManager
from research_platform.toji_os.shutdown_manager import ShutdownManager
from research_platform.toji_os.events import KernelBooted, KernelShutdown

logger = logging.getLogger(__name__)


class TOJIOSOrchestrator:
    """Central unified controller managing the entire TOJI V1 control stack."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        
        self._repo = TOJIOSRepository()
        self._kernel = OSKernel()
        self._workspace = WorkspaceManager()
        self._module_registry = ModuleRegistry()
        self._startup = StartupManager()
        self._shutdown = ShutdownManager()

    @property
    def repository(self) -> TOJIOSRepository:
        return self._repo

    @property
    def module_registry(self) -> ModuleRegistry:
        return self._module_registry

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("TOJIOS: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── Actions ──────────────────────────────────────────────────────

    def boot_kernel(self, session_id: str, user_id: str, plugins: List[Any]) -> OSSession:
        session = self._kernel.initialize_session(session_id, user_id)
        self._repo.save_session(session)
        
        # Invoke startup sequence
        success = self._startup.boot_subsystems(plugins)
        if not success:
            raise RuntimeError("OS Boot Failed: Subsystems failed to boot.")

        self._event_bus.publish(KernelBooted(payload={"session_id": session_id}))
        self._log_downstream_registries(session_id, "OS_KERNEL_SESSION", f"Kernel Booted: user={user_id}")
        return session

    def shutdown_kernel(self, session_id: str, plugins: List[Any]) -> OSSession:
        sess = self._repo.get_session(session_id)
        if not sess:
            raise ValueError(f"Session '{session_id}' not found.")

        updated = sess.model_copy(update={"active": False})
        self._repo.save_session(updated)
        
        # Invoke clean shutdown
        self._shutdown.shutdown_subsystems(plugins)
        
        self._event_bus.publish(KernelShutdown(payload={"session_id": session_id}))
        self._log_downstream_registries(session_id, "OS_KERNEL_SESSION", "Kernel Shutdown Completed")
        return updated

    def load_workspace(self, root_path: str, name: str, strategies: List[str]) -> WorkspaceState:
        state = self._workspace.load_workspace(root_path, name, strategies)
        self._repo.save_workspace(state)
        return state

    def _log_downstream_registries(self, ref_id: str, element_type: str, message: str) -> None:
        # 1. Institutional Memory (R16)
        mem = self._get_memory_orchestrator()
        if mem:
            try:
                mem.publish_memory("observability", {
                    "ref_id": ref_id,
                    "type": element_type,
                    "message": message
                })
            except Exception as e:
                logger.error("TOJIOS Audit: Failed to write to memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg = self._get_kg_orchestrator()
        if kg:
            try:
                kg.register_node(
                    node_id=ref_id,
                    node_type=element_type,
                    subsystem="toji_os",
                    event="KernelUpdated",
                    author="toji_os",
                    properties={"message": message}
                )
            except Exception as e:
                logger.error("TOJIOS Audit: Failed to write to graph: %s", e)

        # 3. Operations Center (R30.5)
        ops = self._get_ops_orchestrator()
        if ops:
            try:
                ops.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("TOJIOS: Failed to refresh operations center: %s", e)
