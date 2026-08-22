"""REST API Router implementation for the Dashboard Platform."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query

from dashboard.core.interfaces import IDashboardRepository, IDashboardStateStore
from dashboard.health.health_monitor import HealthMonitor
from dashboard.aggregator.event_aggregator import DashboardEventAggregator

logger = logging.getLogger(__name__)


def create_api_router(
    state_store: IDashboardStateStore,
    repository: IDashboardRepository,
    health_monitor: HealthMonitor,
    event_aggregator: DashboardEventAggregator,
    container: Any | None = None,
) -> APIRouter:
    """Factory creating APIRouter with dependency injection."""
    router = APIRouter()

    @router.get("/dashboard")
    async def get_dashboard(
        symbol: Optional[str] = Query(None, description="Ticker symbol filter"),
        timeframe: Optional[str] = Query(None, description="Timeframe filter"),
    ) -> Any:
        """Retrieve unified dashboard snapshots. Returns list of snapshots or a single match."""
        if symbol and timeframe:
            snap = state_store.get_snapshot(symbol, timeframe)
            if snap:
                return snap.model_dump(mode="json")
            return {}
        
        snaps = state_store.get_all_snapshots()
        if symbol:
            snaps = [s for s in snaps if s.symbol.upper() == symbol.upper()]
        if timeframe:
            snaps = [s for s in snaps if s.timeframe.lower() == timeframe.lower()]
        return [s.model_dump(mode="json") for s in snaps]

    @router.get("/health")
    async def get_health() -> Dict[str, Any]:
        """Retrieve platform-wide operational health status of all subsystems."""
        health = health_monitor.get_health_status()
        return {k: v.model_dump(mode="json") for k, v in health.items()}

    @router.get("/platform/status")
    async def get_platform_status() -> Dict[str, Any]:
        """Retrieve overall state and details of all modules."""
        if container is None:
            return {"status": "unknown", "error": "DI container not available"}
        try:
            from toji_platform.core.plugin_manager.interfaces import IPluginManager
            pm = container.resolve(IPluginManager)
            stats = pm.get_plugin_lifecycle_stats()
            return {"status": "active", "modules": stats}
        except Exception as e:
            logger.error("Error in get_platform_status: %s", e)
            return {"status": "error", "message": str(e)}

    @router.get("/platform/heartbeat")
    async def get_platform_heartbeat() -> Dict[str, Any]:
        """Retrieve latest heartbeats of all modules."""
        if container is None:
            return {"status": "unknown", "error": "DI container not available"}
        try:
            hs = container.resolve("heartbeat_scheduler")
            return hs.get_latest_heartbeats()
        except Exception as e:
            logger.error("Error in get_platform_heartbeat: %s", e)
            return {"status": "error", "message": str(e)}

    @router.get("/platform/modules")
    async def get_platform_modules() -> List[Dict[str, Any]]:
        """Retrieve static dependency list of loaded plugins."""
        if container is None:
            return []
        try:
            from toji_platform.core.plugin_manager.interfaces import IPluginManager
            pm = container.resolve(IPluginManager)
            plugins = pm.list_plugins()
            
            result = []
            for p in plugins:
                result.append({
                    "id": str(p.plugin_id),
                    "name": p.name,
                    "version": p.version,
                    "dependencies": [str(d) for d in p.dependencies]
                })
            return result
        except Exception as e:
            logger.error("Error in get_platform_modules: %s", e)
            return []

    @router.get("/platform/events")
    async def get_platform_events() -> List[Dict[str, Any]]:
        """Retrieve the latest 100 event dispatches timeline."""
        if container is None:
            return []
        try:
            from toji_platform.core.event_bus.interfaces import IEventBus
            eb = container.resolve(IEventBus)
            if hasattr(eb, "get_timeline"):
                return eb.get_timeline()
            return []
        except Exception as e:
            logger.error("Error in get_platform_events: %s", e)
            return []

    @router.get("/runtime/status")
    async def get_runtime_status() -> Dict[str, Any]:
        """Retrieve overall platform runtime status, mode, and recovery stats."""
        status = {"status": "inactive", "uptime": 0, "mode": "unknown", "recovery_attempts": {}}
        if container is not None:
            try:
                from toji_platform.services.metrics_service import MetricsService
                if container.has(MetricsService):
                    metrics_svc = container.resolve(MetricsService)
                    summary = metrics_svc.get_summary()
                    status["status"] = "active" if summary.get("uptime_seconds", 0) > 0 else "inactive"
                    status["uptime"] = summary.get("uptime_seconds", 0)
                
                from toji_platform.core.configuration import IConfigProvider
                if container.has(IConfigProvider):
                    cfg = container.resolve(IConfigProvider)
                    status["mode"] = str(cfg.get("market_gateway.provider_mode") or "replay")
            except Exception as e:
                logger.error("DashboardAPI: Error getting runtime status: %s", e)
        return status

    @router.get("/runtime/metrics")
    async def get_runtime_metrics() -> Dict[str, Any]:
        """Retrieve current metrics snapshot."""
        if container is not None:
            try:
                from toji_platform.services.metrics_service import MetricsService
                if container.has(MetricsService):
                    metrics_svc = container.resolve(MetricsService)
                    return metrics_svc.get_current()
            except Exception as e:
                logger.error("DashboardAPI: Error resolving MetricsService: %s", e)
        return {}

    @router.get("/runtime/metrics/history")
    async def get_runtime_metrics_history(limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve historical metrics snapshots."""
        if container is not None:
            try:
                from toji_platform.services.metrics_service import MetricsService
                if container.has(MetricsService):
                    metrics_svc = container.resolve(MetricsService)
                    return metrics_svc.get_history(count=limit)
            except Exception as e:
                logger.error("DashboardAPI: Error resolving MetricsService history: %s", e)
        return []

    @router.get("/journal/trades")
    async def get_journal_trades(
        start: Optional[str] = None,
        end: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve trade journal entries."""
        if container is not None:
            try:
                from toji_platform.services.trade_journal import TradeJournal
                from datetime import date
                if container.has(TradeJournal):
                    tj = container.resolve(TradeJournal)
                    start_date = date.fromisoformat(start) if start else None
                    end_date = date.fromisoformat(end) if end else None
                    return tj.query(start_date=start_date, end_date=end_date, symbol=symbol)
            except Exception as e:
                logger.error("DashboardAPI: Error querying TradeJournal: %s", e)
        return []

    @router.get("/journal/trades/summary")
    async def get_journal_trades_summary() -> Dict[str, Any]:
        """Retrieve daily trade stats / summary."""
        if container is not None:
            try:
                from toji_platform.services.trade_journal import TradeJournal
                if container.has(TradeJournal):
                    tj = container.resolve(TradeJournal)
                    return tj.get_stats()
            except Exception as e:
                logger.error("DashboardAPI: Error getting TradeJournal summary: %s", e)
        return {"total_entries": 0, "buffer_size": 0, "running": False}

    @router.get("/journal/events/stats")
    async def get_journal_events_stats() -> Dict[str, Any]:
        """Retrieve Replay Journal stats."""
        if container is not None:
            try:
                from toji_platform.services.replay_journal import ReplayJournal
                if container.has(ReplayJournal):
                    rj = container.resolve(ReplayJournal)
                    return rj.get_stats()
            except Exception as e:
                logger.error("DashboardAPI: Error getting ReplayJournal stats: %s", e)
        return {"total_events": 0, "buffer_size": 0, "running": False}

    @router.get("/replay/status")
    async def get_replay_status() -> Dict[str, Any]:
        """Retrieve Replay system status."""
        status = {"status": "inactive", "replayed_events": 0}
        if container is not None:
            try:
                from toji_platform.services.replay_journal import ReplayJournal
                if container.has(ReplayJournal):
                    rj = container.resolve(ReplayJournal)
                    stats = rj.get_stats()
                    status["status"] = "active" if stats.get("running") else "inactive"
                    status["total_recorded"] = stats.get("total_events", 0)
            except Exception as e:
                logger.error("DashboardAPI: Error getting Replay status: %s", e)
        return status

    @router.get("/reports/daily")
    async def get_reports_daily(day: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve the latest or requested daily report."""
        import os
        from datetime import datetime, timezone
        target_day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report_path = f"data/reports/{target_day}.md"
        if os.path.exists(report_path):
            try:
                with open(report_path, "r") as f:
                    content = f.read()
                return {"date": target_day, "found": True, "content": content}
            except Exception as e:
                logger.error("DashboardAPI: Error reading daily report: %s", e)
        return {"date": target_day, "found": False, "content": ""}


    @router.get("/market")
    async def get_market(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve the latest Market State observations."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.market_state:
                results.append({"symbol": s.symbol, "timeframe": s.timeframe, "market_state": s.market_state})
        return results

    @router.get("/market/regime")
    async def get_market_regime(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve latest regime analysis."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.market_state and s.market_state.get("regime_analysis"):
                results.append({
                    "symbol": s.symbol,
                    "timeframe": s.timeframe,
                    "regime": s.market_state["regime_analysis"],
                })
        return results

    @router.get("/market/trend")
    async def get_market_trend(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve latest detailed trend analysis."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.market_state and s.market_state.get("trend_analysis"):
                results.append({
                    "symbol": s.symbol,
                    "timeframe": s.timeframe,
                    "trend": s.market_state["trend_analysis"],
                })
        return results

    @router.get("/market/volatility")
    async def get_market_volatility(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve latest volatility analysis."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.market_state and s.market_state.get("volatility_analysis"):
                results.append({
                    "symbol": s.symbol,
                    "timeframe": s.timeframe,
                    "volatility": s.market_state["volatility_analysis"],
                })
        return results

    @router.get("/market/liquidity")
    async def get_market_liquidity(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve latest liquidity analysis."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.market_state and s.market_state.get("liquidity_analysis"):
                results.append({
                    "symbol": s.symbol,
                    "timeframe": s.timeframe,
                    "liquidity": s.market_state["liquidity_analysis"],
                })
        return results

    @router.get("/market/orderflow")
    async def get_market_orderflow(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve latest order flow analysis."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.market_state and s.market_state.get("order_flow_analysis"):
                results.append({
                    "symbol": s.symbol,
                    "timeframe": s.timeframe,
                    "orderflow": s.market_state["order_flow_analysis"],
                })
        return results

    @router.get("/market/volume_profile")
    async def get_market_volume_profile(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve latest volume profile analysis."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.market_state and s.market_state.get("volume_profile_analysis"):
                results.append({
                    "symbol": s.symbol,
                    "timeframe": s.timeframe,
                    "volume_profile": s.market_state["volume_profile_analysis"],
                })
        return results

    @router.get("/market/correlation")
    async def get_market_correlation(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve latest asset correlation analysis."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.market_state and s.market_state.get("correlation_analysis"):
                results.append({
                    "symbol": s.symbol,
                    "timeframe": s.timeframe,
                    "correlation": s.market_state["correlation_analysis"],
                })
        return results

    @router.get("/market/confidence")
    async def get_market_confidence(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve latest market confidence summary."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.market_state and s.market_state.get("market_confidence"):
                results.append({
                    "symbol": s.symbol,
                    "timeframe": s.timeframe,
                    "confidence": s.market_state["market_confidence"],
                })
        return results

    @router.get("/market/intelligence")
    async def get_market_intelligence(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve complete market intelligence bundle."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.market_state and s.market_state.get("market_intelligence"):
                results.append({
                    "symbol": s.symbol,
                    "timeframe": s.timeframe,
                    "intelligence": s.market_state["market_intelligence"],
                })
        return results

    @router.get("/patterns")
    async def get_patterns(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve the latest detected chart patterns."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.pattern_state:
                results.append({"symbol": s.symbol, "timeframe": s.timeframe, "pattern_state": s.pattern_state})
        return results

    @router.get("/confluence")
    async def get_confluence(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve the latest confluence scores."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.confluence:
                results.append({"symbol": s.symbol, "timeframe": s.timeframe, "confluence": s.confluence})
        return results

    def _resolve_confluence_states(sym: Optional[str] = None, tf: Optional[str] = None) -> List[Dict[str, Any]]:
        """Helper: resolve confluence states from the DI container's ConfluenceStateStore."""
        if container is None:
            return []
        try:
            from confluence.core.interfaces import IConfluenceStateStore
            if not container.has(IConfluenceStateStore):
                return []
            css = container.resolve(IConfluenceStateStore)
            results = []
            # Iterate over dashboard snapshots to find symbols/timeframes
            snaps = state_store.get_all_snapshots()
            seen = set()
            for s in snaps:
                if sym and s.symbol.upper() != sym.upper():
                    continue
                if tf and s.timeframe.lower() != tf.lower():
                    continue
                key = (s.symbol, s.timeframe)
                if key in seen:
                    continue
                seen.add(key)
                c_snap = css.get_snapshot(s.symbol)
                if c_snap and s.timeframe in c_snap.states:
                    state = c_snap.states[s.timeframe]
                    results.append(state.model_dump(mode="json"))
            return results
        except Exception as e:
            logger.error("DashboardAPI: Error resolving confluence states: %s", e)
            return []

    @router.get("/confluence/score")
    async def get_confluence_score(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve component scores and overall confluence score."""
        states = _resolve_confluence_states(symbol, timeframe)
        results = []
        for st in states:
            score = st.get("score", {})
            results.append({
                "symbol": st.get("symbol"),
                "timeframe": st.get("timeframe"),
                "overall_score": score.get("overall_score"),
                "trend_score": score.get("trend_score"),
                "structure_score": score.get("structure_score"),
                "liquidity_score": score.get("liquidity_score"),
                "zone_score": score.get("zone_score"),
                "volume_score": score.get("volume_score"),
                "regime_score": score.get("regime_score"),
                "session_score": score.get("session_score"),
                "mtf_score": score.get("mtf_score"),
                "correlation_score": score.get("correlation_score"),
                "pattern_score": score.get("pattern_score"),
                "quality_score": score.get("quality_score"),
                "conflict_penalty": score.get("conflict_penalty"),
            })
        return results

    @router.get("/confluence/grade")
    async def get_confluence_grade(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve current setup grade."""
        states = _resolve_confluence_states(symbol, timeframe)
        results = []
        for st in states:
            score = st.get("score", {})
            results.append({
                "symbol": st.get("symbol"),
                "timeframe": st.get("timeframe"),
                "grade": score.get("setup_grade"),
                "overall_score": score.get("overall_score"),
            })
        return results

    @router.get("/confluence/opportunity")
    async def get_confluence_opportunity(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve opportunity quality metrics."""
        states = _resolve_confluence_states(symbol, timeframe)
        results = []
        for st in states:
            score = st.get("score", {})
            opp = score.get("opportunity")
            if opp:
                results.append({
                    "symbol": st.get("symbol"),
                    "timeframe": st.get("timeframe"),
                    "opportunity": opp,
                })
        return results

    @router.get("/confluence/risk_flags")
    async def get_confluence_risk_flags(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve active risk flags."""
        states = _resolve_confluence_states(symbol, timeframe)
        results = []
        for st in states:
            score = st.get("score", {})
            flags = score.get("risk_flags", [])
            results.append({
                "symbol": st.get("symbol"),
                "timeframe": st.get("timeframe"),
                "risk_flags": flags,
                "active_count": sum(1 for f in flags if f.get("active")),
            })
        return results

    @router.get("/confluence/explanation")
    async def get_confluence_explanation(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve structured trade explanations."""
        states = _resolve_confluence_states(symbol, timeframe)
        results = []
        for st in states:
            score = st.get("score", {})
            expl = score.get("explanation")
            if expl:
                results.append({
                    "symbol": st.get("symbol"),
                    "timeframe": st.get("timeframe"),
                    "explanation": expl,
                })
        return results

    @router.get("/confluence/summary")
    async def get_confluence_summary(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve combined confluence summary (scores, grade, opportunity, risk flags, explanation)."""
        states = _resolve_confluence_states(symbol, timeframe)
        results = []
        for st in states:
            score = st.get("score", {})
            results.append({
                "symbol": st.get("symbol"),
                "timeframe": st.get("timeframe"),
                "overall_score": score.get("overall_score"),
                "grade": score.get("setup_grade"),
                "scores": {
                    "trend": score.get("trend_score"),
                    "structure": score.get("structure_score"),
                    "liquidity": score.get("liquidity_score"),
                    "zone": score.get("zone_score"),
                    "volume": score.get("volume_score"),
                    "regime": score.get("regime_score"),
                    "session": score.get("session_score"),
                    "mtf": score.get("mtf_score"),
                    "correlation": score.get("correlation_score"),
                    "pattern": score.get("pattern_score"),
                    "quality": score.get("quality_score"),
                },
                "conflict_penalty": score.get("conflict_penalty"),
                "opportunity": score.get("opportunity"),
                "risk_flags": score.get("risk_flags", []),
                "explanation": score.get("explanation"),
                "supporting_factors": score.get("supporting_factors", []),
                "conflicting_factors": score.get("conflicting_factors", []),
            })
        return results


    @router.get("/strategy")
    async def get_strategy(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve the latest strategy setup signals."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.strategy:
                results.append({"symbol": s.symbol, "timeframe": s.timeframe, "strategy": s.strategy})
        return results

    @router.get("/risk")
    async def get_risk(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve the latest risk evaluation assessments."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.risk_assessment:
                results.append({"symbol": s.symbol, "timeframe": s.timeframe, "risk_assessment": s.risk_assessment})
        return results

    @router.get("/position-size")
    async def get_position_size(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve the latest capital allocation and position sizing details."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.position_size:
                results.append({"symbol": s.symbol, "timeframe": s.timeframe, "position_size": s.position_size})
        return results

    @router.get("/system")
    async def get_system() -> Dict[str, Any]:
        """Retrieve overall platform config details and system parameters."""
        snaps = state_store.get_all_snapshots()
        symbols = list(set(s.symbol for s in snaps))
        timeframes = list(set(s.timeframe for s in snaps))
        return {
            "status": "online",
            "active_symbols": symbols,
            "active_timeframes": timeframes,
            "snapshot_count": len(snaps),
        }

    @router.get("/events")
    async def get_events(
        symbol: Optional[str] = Query(None),
        timeframe: Optional[str] = Query(None),
    ) -> List[Dict[str, Any]]:
        """Retrieve historical timeline events captured by the event aggregator."""
        hist = event_aggregator.get_events_history()
        if symbol:
            hist = [e for e in hist if e.symbol.upper() == symbol.upper()]
        if timeframe:
            hist = [e for e in hist if e.timeframe.lower() == timeframe.lower()]
        
        # Sort chronologically, newest first
        sorted_events = sorted(hist, key=lambda e: e.timestamp, reverse=True)
        return [e.model_dump(mode="json") for e in sorted_events]

    @router.get("/executions")
    async def get_executions(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Retrieve the latest execution states."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.execution_state:
                results.append({"symbol": s.symbol, "timeframe": s.timeframe, "execution_state": s.execution_state})
        return results

    @router.get("/executions/metrics")
    async def get_execution_metrics(
        symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> Any:
        """Fetch latency and slippage analytics from execution states."""
        snaps = state_store.get_all_snapshots()
        results = []
        for s in snaps:
            if symbol and s.symbol.upper() != symbol.upper():
                continue
            if timeframe and s.timeframe.lower() != timeframe.lower():
                continue
            if s.execution_state and "result" in s.execution_state and s.execution_state["result"]:
                res = s.execution_state["result"]
                if "metrics" in res and res["metrics"]:
                    results.append({
                        "symbol": s.symbol,
                        "timeframe": s.timeframe,
                        "metrics": res["metrics"]
                    })
        return results

    @router.get("/executions/health")
    async def get_execution_health() -> Any:
        """Fetch execution health parameters."""
        health = health_monitor.get_health_status()
        if "execution_engine" in health:
            return health["execution_engine"].model_dump(mode="json")
        return {
            "status": "HEALTHY",
            "last_update": datetime.now(timezone.utc).isoformat(),
            "processing_latency_ms": 0.05,
            "message_count": 0,
            "replay_status": "LIVE"
        }

    @router.get("/executions/analytics")
    async def get_executions_analytics() -> Any:
        """Fetch throughput, latency, and fill statistics from execution analytics."""
        from execution_engine.analysis.analytics import ExecutionAnalyticsCalculator
        if container and container.has(ExecutionAnalyticsCalculator):
            try:
                calc = container.resolve(ExecutionAnalyticsCalculator)
                return calc.get_summary()
            except Exception as e:
                logger.error("DashboardAPI: Failed to resolve Analytics: %s", e)
        return {
            "success_rate": 1.0,
            "fill_rate": 0.0,
            "partial_fill_rate": 0.0,
            "average_slippage": 0.0,
            "average_commission": 0.0,
            "average_latency_ms": 0.05,
            "retry_rate": 0.0,
            "orders_per_second": 0.0,
            "queue_depth": 0,
            "peak_queue_size": 0,
        }

    @router.get("/executions/audit")
    async def get_executions_audit(
        execution_id: Optional[str] = Query(None, description="Optional filter by execution ID")
    ) -> List[Any]:
        """Fetch immutable audit records detailing order lifecycles."""
        from execution_engine.core.interfaces import IExecutionRepository
        if container and container.has(IExecutionRepository):
            try:
                repo = container.resolve(IExecutionRepository)
                records = repo.get_audit_records(execution_id)
                return [r.model_dump(mode="json") for r in records]
            except Exception as e:
                logger.error("DashboardAPI: Failed to retrieve audit logs: %s", e)
        return []

    @router.get("/executions/capabilities")
    async def get_executions_capabilities() -> Any:
        """Introspect capability matrices for the registered brokers."""
        from execution_engine.core.oms import BrokerManager
        if container and container.has(BrokerManager):
            try:
                mgr = container.resolve(BrokerManager)
                paper = mgr.get_broker("paper")
                binance = mgr.get_broker("binance")
                return {
                    "paper": paper.get_capabilities().model_dump(mode="json") if paper else {},
                    "binance": binance.get_capabilities().model_dump(mode="json") if binance else {},
                }
            except Exception as e:
                logger.error("DashboardAPI: Failed to retrieve capabilities: %s", e)
        return {
            "paper": {
                "supports_market": True,
                "supports_limit": True,
                "supports_stop": True,
                "supports_trailing_stop": True,
                "supports_reduce_only": True,
                "supports_post_only": True,
                "supports_oco": True,
                "supports_iceberg": True,
                "supports_brackets": True,
                "supports_twap": True,
                "supports_vwap": True,
                "max_leverage": 20.0,
                "precision": 4,
                "tick_size": 0.01,
                "min_notional": 10.0,
            },
            "binance": {
                "supports_market": True,
                "supports_limit": True,
                "supports_stop": True,
                "supports_trailing_stop": True,
                "supports_reduce_only": True,
                "supports_post_only": True,
                "supports_oco": True,
                "supports_iceberg": True,
                "supports_brackets": False,
                "supports_twap": False,
                "supports_vwap": False,
                "max_leverage": 125.0,
                "precision": 8,
                "tick_size": 0.00000001,
                "min_notional": 10.0,
            }
        }

    @router.get("/portfolio/snapshot")
    async def get_portfolio_snapshot() -> Any:
        """Fetch the full current Portfolio Snapshot."""
        from portfolio_engine.core.state import PortfolioStateStore
        if container and container.has(PortfolioStateStore):
            try:
                store = container.resolve(PortfolioStateStore)
                return store.get_current_snapshot().model_dump(mode="json")
            except Exception as e:
                logger.error("DashboardAPI: Failed to resolve PortfolioStateStore: %s", e)
        return {
            "snapshot_id": "mock-snapshot-id",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "positions": {},
            "closed_positions": [],
            "metrics": {
                "total_realized_pnl": 0.0,
                "total_unrealized_pnl": 0.0,
                "gross_exposure": 0.0,
                "net_exposure": 0.0,
                "portfolio_value": 100000.0,
                "margin_used": 0.0,
                "leverage_ratio": 0.0
            },
            "health": {
                "status": "HEALTHY",
                "drawdown": 0.0,
                "leverage_ratio": 0.0,
                "risk_exposure_ratio": 0.0
            }
        }

    @router.get("/portfolio/positions")
    async def get_portfolio_positions() -> Any:
        """Fetch list of open and closed positions."""
        from portfolio_engine.core.state import PortfolioStateStore
        if container and container.has(PortfolioStateStore):
            try:
                store = container.resolve(PortfolioStateStore)
                snap = store.get_current_snapshot()
                return {
                    "open": [p.model_dump(mode="json") for p in snap.positions.values()],
                    "closed": [p.model_dump(mode="json") for p in snap.closed_positions],
                }
            except Exception as e:
                logger.error("DashboardAPI: Failed to resolve PortfolioStateStore: %s", e)
        return {"open": [], "closed": []}

    @router.get("/portfolio/metrics")
    async def get_portfolio_metrics() -> Any:
        """Fetch aggregated metrics and statistics."""
        from portfolio_engine.core.state import PortfolioStateStore
        if container and container.has(PortfolioStateStore):
            try:
                store = container.resolve(PortfolioStateStore)
                snap = store.get_current_snapshot()
                stats = store.get_statistics()
                return {
                    "metrics": snap.metrics.model_dump(mode="json"),
                    "health": snap.health.model_dump(mode="json"),
                    "statistics": stats.model_dump(mode="json"),
                }
            except Exception as e:
                logger.error("DashboardAPI: Failed to resolve PortfolioStateStore: %s", e)
        return {
            "metrics": {
                "total_realized_pnl": 0.0,
                "total_unrealized_pnl": 0.0,
                "gross_exposure": 0.0,
                "net_exposure": 0.0,
                "portfolio_value": 100000.0,
                "margin_used": 0.0,
                "leverage_ratio": 0.0
            },
            "health": {
                "status": "HEALTHY",
                "drawdown": 0.0,
                "leverage_ratio": 0.0,
                "risk_exposure_ratio": 0.0
            },
            "statistics": {
                "winning_pct": 0.0,
                "losing_pct": 0.0,
                "average_win": 0.0,
                "average_loss": 0.0,
                "profit_factor": 0.0,
                "total_trades": 0
            }
        }
    @router.get("/exchange/status")
    async def get_exchange_status() -> Dict[str, Any]:
        if container is not None:
            try:
                from market_gateway.providers.binance.exchange import BinanceExchangeProvider
                if container.has(BinanceExchangeProvider):
                    provider = container.resolve(BinanceExchangeProvider)
                    return provider.health()
            except Exception as e:
                logger.error("Error in get_exchange_status: %s", e)
        return {"status": "inactive"}

    @router.get("/exchange/account")
    async def get_exchange_account() -> Dict[str, Any]:
        if container is not None:
            try:
                from market_gateway.providers.binance.exchange import BinanceExchangeProvider
                if container.has(BinanceExchangeProvider):
                    provider = container.resolve(BinanceExchangeProvider)
                    return provider.get_account()
            except Exception as e:
                logger.error("Error in get_exchange_account: %s", e)
        return {}

    @router.get("/exchange/balances")
    async def get_exchange_balances() -> Dict[str, float]:
        if container is not None:
            try:
                from market_gateway.providers.binance.exchange import BinanceExchangeProvider
                if container.has(BinanceExchangeProvider):
                    provider = container.resolve(BinanceExchangeProvider)
                    return provider.get_balances()
            except Exception as e:
                logger.error("Error in get_exchange_balances: %s", e)
        return {}

    @router.get("/exchange/open_orders")
    async def get_exchange_open_orders(symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        if container is not None:
            try:
                from market_gateway.providers.binance.exchange import BinanceExchangeProvider
                if container.has(BinanceExchangeProvider):
                    provider = container.resolve(BinanceExchangeProvider)
                    return provider.get_open_orders(symbol)
            except Exception as e:
                logger.error("Error in get_exchange_open_orders: %s", e)
        return []

    @router.get("/exchange/open_positions")
    async def get_exchange_open_positions() -> List[Dict[str, Any]]:
        if container is not None:
            try:
                from market_gateway.providers.binance.exchange import BinanceExchangeProvider
                if container.has(BinanceExchangeProvider):
                    provider = container.resolve(BinanceExchangeProvider)
                    return provider.get_positions()
            except Exception as e:
                logger.error("Error in get_exchange_open_positions: %s", e)
        return []

    @router.get("/exchange/latency")
    async def get_exchange_latency() -> Dict[str, Any]:
        if container is not None:
            try:
                from market_gateway.providers.binance.exchange import BinanceExchangeProvider
                if container.has(BinanceExchangeProvider):
                    provider = container.resolve(BinanceExchangeProvider)
                    health_status = provider.health()
                    return {"latency_ms": health_status.get("latency_ms", 0.0)}
            except Exception as e:
                logger.error("Error in get_exchange_latency: %s", e)
        return {"latency_ms": 0.0}

    @router.get("/exchange/server_time")
    async def get_exchange_server_time() -> Dict[str, Any]:
        if container is not None:
            try:
                from market_gateway.providers.binance.exchange import BinanceExchangeProvider
                if container.has(BinanceExchangeProvider):
                    provider = container.resolve(BinanceExchangeProvider)
                    return {"server_time": provider.get_server_time()}
            except Exception as e:
                logger.error("Error in get_exchange_server_time: %s", e)
        return {"server_time": 0}

    @router.get("/exchange/health")
    async def get_exchange_health() -> Dict[str, Any]:
        if container is not None:
            try:
                from market_gateway.providers.binance.exchange import BinanceExchangeProvider
                if container.has(BinanceExchangeProvider):
                    provider = container.resolve(BinanceExchangeProvider)
                    health_status = provider.health()
                    return {"status": health_status.get("status", "disconnected"), "connected": health_status.get("ws_connected", False)}
            except Exception as e:
                logger.error("Error in get_exchange_health: %s", e)
        return {"status": "disconnected", "connected": False}

    @router.get("/trades")
    async def get_trades(symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        if container is not None:
            try:
                from execution_engine.core.interfaces import IExecutionRepository
                if container.has(IExecutionRepository):
                    repo = container.resolve(IExecutionRepository)
                    orders = repo.load_latest_orders(100)
                    if symbol:
                        orders = [o for o in orders if o.symbol == symbol]
                    return [o.model_dump(mode="json") for o in orders if o.state.value == "FILLED"]
            except Exception as e:
                logger.error("Error in get_trades: %s", e)
        return []

    @router.get("/orders")
    async def get_orders(symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        if container is not None:
            try:
                from execution_engine.core.interfaces import IExecutionRepository
                if container.has(IExecutionRepository):
                    repo = container.resolve(IExecutionRepository)
                    orders = repo.load_latest_orders(100)
                    if symbol:
                        orders = [o for o in orders if o.symbol == symbol]
                    return [o.model_dump(mode="json") for o in orders]
            except Exception as e:
                logger.error("Error in get_orders: %s", e)
        return []

    @router.get("/api/v1/risk/status")
    async def get_risk_status() -> List[Dict[str, Any]]:
        """Fetch consolidated risk dashboard snapshot containing exposure, drawdown, and rule assessment status."""
        if container is not None:
            try:
                from risk_engine.core.interfaces import IRiskStateStore
                if container.has(IRiskStateStore):
                    store = container.resolve(IRiskStateStore)
                    snapshots = list(store._snapshots.values())
                    return [s.model_dump(mode="json") for s in snapshots]
            except Exception as e:
                logger.error("Error in get_risk_status REST API: %s", e)
        return []

    @router.get("/api/v1/risk/breakers")
    async def get_risk_breakers() -> Dict[str, Any]:
        """Fetch status of active circuit breakers across all monitored assets."""
        if container is not None:
            try:
                from risk_engine.core.interfaces import IRiskStateStore
                if container.has(IRiskStateStore):
                    store = container.resolve(IRiskStateStore)
                    breakers_info = {}
                    for symbol, snap in store._snapshots.items():
                        for tf, tf_state in snap.states.items():
                            breakers_info[f"{symbol}:{tf}"] = tf_state.circuit_breaker.model_dump(mode="json")
                    return breakers_info
            except Exception as e:
                logger.error("Error in get_risk_breakers REST API: %s", e)
        return {}

    @router.post("/api/v1/risk/killswitch")
    async def trigger_killswitch() -> Dict[str, Any]:
        """Trigger manual emergency stop/killswitch, halting all further order routing."""
        if container is not None:
            try:
                from toji_platform.core.configuration.interfaces import IConfigProvider
                if container.has(IConfigProvider):
                    config = container.resolve(IConfigProvider)
                    config.set("risk.emergency_stop", True)
                    config.set("risk.manual_kill_switch", True)
                    logger.warning("REST API: Manual killswitch/emergency stop triggered successfully.")
                    return {"status": "triggered", "message": "Manual emergency stop has been activated. All routing halted."}
            except Exception as e:
                logger.error("Error triggering manual killswitch: %s", e)
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "Configuration provider not resolved"}

    @router.post("/api/v1/risk/override")
    async def toggle_override(enable: bool = Query(True, description="Enable or disable risk override mode")) -> Dict[str, Any]:
        """Enable or disable risk override mode to bypass safety rules during emergency recovery."""
        if container is not None:
            try:
                from toji_platform.core.configuration.interfaces import IConfigProvider
                if container.has(IConfigProvider):
                    config = container.resolve(IConfigProvider)
                    config.set("risk.risk_override", enable)
                    logger.warning("REST API: Risk override set to: %s", enable)
                    return {"status": "configured", "override_active": enable, "message": f"Risk override mode set to {enable}."}
            except Exception as e:
                logger.error("Error toggling risk override mode: %s", e)
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "Configuration provider not resolved"}

    # ── Sprint 8: Institutional OMS & EMS API Routes ──────────────────

    @router.get("/api/v1/orders/intents")
    async def get_order_intents() -> List[Dict[str, Any]]:
        """Retrieve all order intents (active and terminal)."""
        if container is not None:
            try:
                from execution_engine.oms.oms_core import OmsCore
                if container.has(OmsCore):
                    oms = container.resolve(OmsCore)
                    intents = oms.get_all_intents()
                    return [i.model_dump(mode="json") for i in intents]
            except Exception as e:
                logger.error("DashboardAPI: Error fetching order intents: %s", e)
        return []

    @router.get("/api/v1/orders/active")
    async def get_active_intents() -> List[Dict[str, Any]]:
        """Retrieve active (non-terminal) order intents."""
        if container is not None:
            try:
                from execution_engine.oms.oms_core import OmsCore
                if container.has(OmsCore):
                    oms = container.resolve(OmsCore)
                    intents = oms.get_active_intents()
                    return [i.model_dump(mode="json") for i in intents]
            except Exception as e:
                logger.error("DashboardAPI: Error fetching active intents: %s", e)
        return []

    @router.get("/api/v1/orders/{intent_id}")
    async def get_order_intent_detail(intent_id: str) -> Dict[str, Any]:
        """Retrieve detailed state of a single order intent."""
        if container is not None:
            try:
                from execution_engine.oms.oms_core import OmsCore
                if container.has(OmsCore):
                    oms = container.resolve(OmsCore)
                    intent = oms.get_intent(intent_id)
                    if intent:
                        return intent.model_dump(mode="json")
            except Exception as e:
                logger.error("DashboardAPI: Error fetching intent %s: %s", intent_id, e)
        return {"error": "Intent not found"}

    @router.post("/api/v1/orders/{intent_id}/cancel")
    async def cancel_order_intent(intent_id: str) -> Dict[str, Any]:
        """Request cancellation of a working order intent."""
        if container is not None:
            try:
                from execution_engine.oms.oms_core import OmsCore
                if container.has(OmsCore):
                    oms = container.resolve(OmsCore)
                    intent = oms.cancel_intent(intent_id)
                    return {"status": "cancelled", "intent": intent.model_dump(mode="json")}
            except Exception as e:
                logger.error("DashboardAPI: Error cancelling intent %s: %s", intent_id, e)
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "OMS not available"}

    @router.get("/api/v1/orders/oms/state")
    async def get_oms_state() -> Dict[str, Any]:
        """Retrieve OMS operational state counters."""
        if container is not None:
            try:
                from execution_engine.oms.oms_core import OmsCore
                if container.has(OmsCore):
                    oms = container.resolve(OmsCore)
                    state = oms.get_oms_state()
                    return state.model_dump(mode="json")
            except Exception as e:
                logger.error("DashboardAPI: Error fetching OMS state: %s", e)
        return {
            "total_intents": 0, "active_intents": 0,
            "completed_intents": 0, "rejected_intents": 0,
            "failed_intents": 0, "cancelled_intents": 0,
        }

    @router.get("/api/v1/orders/brokers")
    async def get_broker_statuses() -> List[Dict[str, Any]]:
        """Retrieve connection status for all registered broker adapters."""
        if container is not None:
            try:
                from execution_engine.oms.oms_core import OmsCore
                if container.has(OmsCore):
                    oms = container.resolve(OmsCore)
                    statuses = oms.get_broker_statuses()
                    return [s.model_dump(mode="json") for s in statuses]
            except Exception as e:
                logger.error("DashboardAPI: Error fetching broker statuses: %s", e)
        return []

    @router.get("/api/v1/orders/routing")
    async def get_routing_decisions(intent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve routing decision records."""
        if container is not None:
            try:
                from execution_engine.oms.oms_core import OmsCore
                if container.has(OmsCore):
                    oms = container.resolve(OmsCore)
                    decisions = oms.get_routing_decisions(intent_id)
                    return [d.model_dump(mode="json") for d in decisions]
            except Exception as e:
                logger.error("DashboardAPI: Error fetching routing decisions: %s", e)
        return []

    @router.get("/api/v1/orders/executions")
    async def get_ems_executions() -> List[Dict[str, Any]]:
        """Retrieve active EMS algorithmic execution states."""
        if container is not None:
            try:
                from execution_engine.ems.ems_engine import EmsEngine
                if container.has(EmsEngine):
                    ems = container.resolve(EmsEngine)
                    states = ems.get_all_executions()
                    return [s.model_dump(mode="json") for s in states]
            except Exception as e:
                logger.error("DashboardAPI: Error fetching EMS executions: %s", e)
        return []

    @router.get("/api/v1/orders/executions/active")
    async def get_active_ems_executions() -> List[Dict[str, Any]]:
        """Retrieve currently running EMS algorithmic executions."""
        if container is not None:
            try:
                from execution_engine.ems.ems_engine import EmsEngine
                if container.has(EmsEngine):
                    ems = container.resolve(EmsEngine)
                    states = ems.get_active_executions()
                    return [s.model_dump(mode="json") for s in states]
            except Exception as e:
                logger.error("DashboardAPI: Error fetching active EMS executions: %s", e)
        return []

    @router.post("/api/v1/orders/recovery")
    async def trigger_recovery() -> Dict[str, Any]:
        """Trigger manual OMS crash recovery reconciliation."""
        if container is not None:
            try:
                from execution_engine.oms.recovery import RecoveryManager
                from execution_engine.oms.oms_core import OmsCore
                if container.has(RecoveryManager) and container.has(OmsCore):
                    recovery = container.resolve(RecoveryManager)
                    oms = container.resolve(OmsCore)
                    persisted = oms.get_all_intents()
                    results = recovery.reconcile(persisted, oms._intent_store)
                    return {"status": "completed", "reconciled": results}
            except Exception as e:
                logger.error("DashboardAPI: Error triggering recovery: %s", e)
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "Recovery manager not available"}

    return router

