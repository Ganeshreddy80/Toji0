# SPRINT 003 — PA-0 DISCOVERY GATE REPORT

**Author:** TOJI CTO / Lead Architect  
**Date:** 2026-08-10T13:52:00Z  
**Governance:** Master Architecture Governance — Sprint 003 / Stage PA-0  
**Predecessor:** `CTO-MASTER-ARCHITECTURE-GATE.md` — **PASS**  
**Production Python Files Modified:** `0`

---

## 1. SOURCE FILES INSPECTED

| File | Path | Lines | Purpose |
|---|---|---|---|
| `interfaces.py` | `research_platform/price_action/interfaces.py` | 42 | `IPriceActionOrchestrator` abstract interface |
| `orchestrator.py` | `research_platform/price_action/orchestrator.py` | 261 | `PriceActionOrchestrator` full implementation |
| `models.py` | `research_platform/price_action/models.py` | 64 | Domain model Pydantic classes |
| `events.py` | `research_platform/price_action/events.py` | 22 | `StructureDetected`, `ImbalanceDetected`, `SessionUpdated` |
| `repository.py` | `research_platform/price_action/repository.py` | 156 | `PriceActionRepository` thread-safe in-memory + PostgreSQL persistence |
| `plugin.py` | `research_platform/price_action/plugin.py` | 44 | `PriceActionPlugin` DI registration |
| `run_paper_trading.py` | `scripts/run_paper_trading.py` | 1196 | Active paper-trading tick loop — all PA invocations |
| `validate_sprint_pipeline.py` | `scripts/validate_sprint_pipeline.py` | 200 | Pipeline validation script — resolves PA from DI container |
| `live_trading/plugin.py` | `research_platform/live_trading/plugin.py` | 292 | Live-trading plugin — also accesses `_bars` directly |
| `test_sprint2_intelligence.py` | `research_platform/tests/test_sprint2_intelligence.py` | 263 | Existing PA test suite (2 PA test functions + direct `_bars` access) |
| `startup.py` | `research_platform/platform/startup.py` | 207 | Plugin boot priority table and sorted initialization |

---

## 2. PUBLIC INTERFACE INVENTORY

### `IPriceActionOrchestrator` (`interfaces.py:12-41`)

| Method | Signature | Purpose | In Interface | Implemented |
|---|---|---|---|---|
| `process_tick` | `(symbol: str, price: float, timestamp: datetime, volume: float = 0.0) -> None` | Ingest tick: update tick history, VWAP, aggregate 1m bars, run detectors on bar close | ✅ | ✅ |
| `get_swings` | `(symbol: str) -> List[SwingPoint]` | Return all detected swing highs/lows | ✅ | ✅ |
| `get_structure_changes` | `(symbol: str) -> List[MarketStructureChange]` | Return BOS / CHOCH events | ✅ | ✅ |
| `get_blocks` | `(symbol: str) -> List[BlockStructure]` | Return Order Blocks, Breaker Blocks, Mitigation Blocks | ✅ | ✅ |
| `get_gaps` | `(symbol: str) -> List[ImbalanceGap]` | Return active Fair Value Gaps | ✅ | ✅ |
| `get_atr` | `(symbol: str) -> float` | Return current 14-bar Average True Range | ✅ | ✅ |
| `get_vwap` | `(symbol: str) -> float` | Return cumulative session VWAP | ✅ | ✅ |
| **`get_bars`** | **MISSING** | **Return aggregated 1m OHLCV bars list for a symbol** | ❌ **ABSENT** | ❌ **NOT IMPLEMENTED** |

**Finding:** `get_bars()` does not exist anywhere in `IPriceActionOrchestrator` or `PriceActionOrchestrator`.
The only way callers currently access bars data is through the private `_bars` dict directly.

---

## 3. PRIVATE STATE INVENTORY

All private instance variables of `PriceActionOrchestrator` (`orchestrator.py:24-42`):

| Variable | Type | Owner | Description | Bounded? |
|---|---|---|---|---|
| `_event_bus` | `IEventBus` | constructor arg | EventBus reference for publishing events | — |
| `_repo` | `PriceActionRepository` | constructor arg | Persistent repository for swings, changes, blocks, gaps | — |
| `_container` | `Optional[Any]` | constructor arg | DI container reference (optional) | — |
| `_tick_history` | `Dict[str, List[Dict]]` | internal | Raw tick log per symbol. Keys: `price`, `timestamp`, `volume` | ✅ Capped at 1,000 ticks |
| `_bars` | `Dict[str, List[Dict]]` | internal | Aggregated 1m OHLCV bars per symbol. Keys: `timestamp`, `open`, `high`, `low`, `close`, `volume` | ✅ Capped at 200 bars |
| `_cum_pv` | `Dict[str, float]` | internal | Cumulative price×volume per symbol (VWAP numerator) | Not bounded (grows with ticks, scalar) |
| `_cum_v` | `Dict[str, float]` | internal | Cumulative volume per symbol (VWAP denominator) | Not bounded (grows with ticks, scalar) |
| `_atr` | `Dict[str, float]` | internal | Cached ATR float per symbol | 1 value/symbol |
| `_vwap` | `Dict[str, float]` | internal | Cached VWAP float per symbol | 1 value/symbol |
| `_trend` | `Dict[str, str]` | internal | Current trend bias per symbol: `"BULLISH"` or `"BEARISH"` | 1 value/symbol |

---

## 4. `_bars` EXACT OWNERSHIP & ACCESS MAP

### Ownership
- `_bars` is declared in `orchestrator.py:31` as `self._bars: Dict[str, List[Dict[str, Any]]] = {}`.
- It is **not** listed in `IPriceActionOrchestrator` (the interface has no bars-related method).
- It is **not** returned by any public method.
- It is accessed **internally** by `_aggregate_bar()`, `_run_detectors()`, and `_calculate_atr()`.

### Bar Structure (per entry in the list):
```python
{
    "timestamp": datetime,   # UTC, minute-truncated (second=0, microsecond=0)
    "open":      float,      # First price of the 1m bar
    "high":      float,      # Max price seen in the 1m window
    "low":       float,      # Min price seen in the 1m window
    "close":     float,      # Last price seen in the 1m window
    "volume":    float,      # Cumulative volume for the 1m window
}
```

### External `_bars` Access Map (All Direct Private Callers):

| Caller | File | Line | Access Pattern | Purpose |
|---|---|---|---|---|
| `run_paper_trading.py` | `scripts/run_paper_trading.py` | **284** | `pa_orch._bars.get(symbol, [])` | Feed bars DataFrame into `FeaturePlatformOrchestrator.compute_and_store()` |
| `live_trading/plugin.py` | `research_platform/live_trading/plugin.py` | **199** | `pa_orch._bars.get(symbol, [])` | Same purpose as above — feed into Feature Platform |
| `test_sprint2_intelligence.py` | `research_platform/tests/test_sprint2_intelligence.py` | **61** | `orch._bars[symbol]` (read) | Assert bars were populated after tick ingestion |
| `test_sprint2_intelligence.py` | `research_platform/tests/test_sprint2_intelligence.py` | **83** | `orch._bars[symbol] = [...]` (write) | Directly inject bars for FVG detection test setup |

**Total external `_bars` callers: 4** (2 production callers, 2 test callers).

---

## 5. EVENT SCHEMA MAP

All events defined in `research_platform/price_action/events.py`. All extend `toji_platform.core.event_bus.events.BaseEvent` (frozen dataclasses).

| Event | Class | Defined At | Payload Structure (from publish calls in orchestrator.py) |
|---|---|---|---|
| `StructureDetected` | `StructureDetected(BaseEvent)` | `events.py:10` | `{"swing": swing.model_dump()}` or `{"change": change.model_dump()}` |
| `ImbalanceDetected` | `ImbalanceDetected(BaseEvent)` | `events.py:15` | `{"gap": gap.model_dump()}` |
| `SessionUpdated` | `SessionUpdated(BaseEvent)` | `events.py:20` | **NEVER PUBLISHED** (defined but no publish call exists in `orchestrator.py`) |

**Finding:** `SessionUpdated` is **defined but never published** anywhere in `PriceActionOrchestrator`. No session detection logic exists. This is a defined but unimplemented event.

### EventBus Publish Calls (source lines):

| Event | Published At | Trigger |
|---|---|---|
| `StructureDetected` | `orchestrator.py:118` | On swing HIGH detection |
| `StructureDetected` | `orchestrator.py:130` | On swing LOW detection |
| `StructureDetected` | `orchestrator.py:189` | On bullish BOS/CHOCH |
| `StructureDetected` | `orchestrator.py:214` | On bearish BOS/CHOCH |
| `ImbalanceDetected` | `orchestrator.py:143` | On bullish FVG detection |
| `ImbalanceDetected` | `orchestrator.py:154` | On bearish FVG detection |

---

## 6. EVENTBUS INTEGRATION MAP

| Component | Role | Method |
|---|---|---|
| `PriceActionOrchestrator` | **Publisher only** — calls `self._event_bus.publish(...)` | `publish(event)` |
| `PriceActionOrchestrator` | **No subscriptions** — does not subscribe to any event | — |
| Downstream consumers (strategy, risk) | **Not currently wired** to `StructureDetected` or `ImbalanceDetected` via EventBus in paper runtime | — |

**Finding:** The `EventBus` is used exclusively for outbound publication. No component in the active paper-trading runtime currently subscribes to `StructureDetected` or `ImbalanceDetected`. These events are published but not consumed by any downstream listener.

---

## 7. FEATURE PLATFORM INTEGRATION MAP

| Step | File | Line | Call Pattern |
|---|---|---|---|
| PA ticked | `run_paper_trading.py` | 280 | `pa_orch.process_tick(symbol, price_float, candle.timestamp, volume)` |
| `_bars` accessed (private) | `run_paper_trading.py` | 284 | `bars_list = pa_orch._bars.get(symbol, [])` |
| DataFrame built | `run_paper_trading.py` | 285-288 | `df = pd.DataFrame(bars_list)` if `len(bars_list) > 1` else single-candle fallback |
| Feature Platform computed | `run_paper_trading.py` | 337 | `output_df = feature_platform.compute_and_store(features_to_compute, symbol, df)` |

**Integration boundary is currently via private `_bars` attribute, not via any public API or EventBus event.**

---

## 8. RUNTIME TICK ORDER (ACTUAL — SOURCE VERIFIED)

Execution order in `scripts/run_paper_trading.py` per tick:

```
1. Line 248-274: MarketDataNormalizer.normalize_binance_candle() → OHLCV candle
2. Line 279:     container.resolve(PriceActionOrchestrator)
3. Line 280:     pa_orch.process_tick(symbol, price_float, candle.timestamp, volume)
                  → ticks updated → VWAP updated → bar aggregated → detectors run on bar close
4. Line 284:     bars_list = pa_orch._bars.get(symbol, [])  ← PRIVATE ACCESS
5. Line 290:     container.resolve(FeaturePlatformOrchestrator)
6. Line 337:     feature_platform.compute_and_store(features_to_compute, symbol, df)
7. Line 362+:    StrategyComposer.generate_decision(strategy, symbol, price, indicators)
8. Line 400+:    RiskManagementOrchestrator.validate_order(...)
9. Line 450+:    OmsCore.submit_order(...)
```

---

## 9. PLUGIN BOOT ORDER (ACTUAL — SOURCE VERIFIED)

From `startup.py:64-115`:

```python
sorted_plugins = sorted(plugins, key=get_priority)  # ascending order
```

Relevant boot sequence:
```
Priority 10.0 → FeaturePlatformPlugin   (initializes first)
Priority 10.1 → PriceActionPlugin       (initializes AFTER FeaturePlatform)
Priority 10.2 → MultiTimeframePlugin
Priority 10.3 → ConfluencePlugin
Priority 10.4 → AISignalPlugin
```

**Source-confirmed:** `FeaturePlatformPlugin` DI-registers `FeaturePlatformOrchestrator` **before** `PriceActionPlugin` DI-registers `PriceActionOrchestrator`. Both are available when tick loop starts (tick loop runs after all plugins boot).

---

## 10. EXISTING TEST COVERAGE

| Test File | PA Components Tested | Test Functions | Access Pattern | Gaps |
|---|---|---|---|---|
| `test_sprint2_intelligence.py` | `PriceActionOrchestrator`, `PriceActionRepository`, all models | `test_price_action_swings_and_indicators`, `test_price_action_fvg_imbalances` | Uses `process_tick()` (public), `get_swings()` (public), `get_gaps()` (public), `orch._bars` (private — direct read on line 61, direct write on line 83) | No test for `get_structure_changes()`, `get_blocks()`, `get_atr()`, `get_vwap()` as callable methods; no test for `SessionUpdated`; no memory truncation test; no determinism replay test |

**No other Python test files test `research_platform/price_action/` components directly.** (Confirmed by grep search.)

---

## 11. DIRECT `_bars` CALLERS (COMPLETE INVENTORY)

| # | Caller | File | Line | Type | Access |
|---|---|---|---|---|---|
| 1 | `handle_market_tick()` | `scripts/run_paper_trading.py` | 284 | **Production** | Read: `pa_orch._bars.get(symbol, [])` |
| 2 | `LiveTradingPlugin._on_live_tick()` | `research_platform/live_trading/plugin.py` | 199 | Production | Read: `pa_orch._bars.get(symbol, [])` |
| 3 | `test_price_action_swings_and_indicators()` | `research_platform/tests/test_sprint2_intelligence.py` | 61 | Test | Read: `orch._bars[symbol]` |
| 4 | `test_price_action_fvg_imbalances()` | `research_platform/tests/test_sprint2_intelligence.py` | 83 | Test | **Write**: `orch._bars[symbol] = [...]` (direct bar injection for test setup) |

**PA-1 must create `get_bars()`. PA-2 must update callers #1 and #2. Tests #3 and #4 will also be updated — #4 will use `_run_detectors()` directly or a test-only setup helper.**

---

## 12. EXACT PA-1 CHANGES REQUIRED

**Target:** `research_platform/price_action/interfaces.py` and `research_platform/price_action/orchestrator.py` only.

### `interfaces.py` change:
Add `get_bars` to `IPriceActionOrchestrator`:
```python
def get_bars(self, symbol: str) -> List[Dict[str, Any]]:
    """Return the list of aggregated 1-minute OHLCV bars for a symbol (defensive copy)."""
    pass
```

### `orchestrator.py` change:
Implement `get_bars` on `PriceActionOrchestrator`:
```python
def get_bars(self, symbol: str) -> List[Dict[str, Any]]:
    """Return a defensive copy of the 1m OHLCV bar list for the given symbol."""
    return list(self._bars.get(symbol, []))
```

**A defensive copy (`list(...)`) is required** to prevent callers from mutating internal state.

### New unit tests required (PA-3):
- `test_get_bars_returns_empty_list_for_unknown_symbol()`
- `test_get_bars_returns_correct_bars_after_tick_ingestion()`
- `test_get_bars_returns_defensive_copy()` (mutation of returned list must not affect `_bars`)
- Existing test at line 83 (`orch._bars[symbol] = [...]`) must be refactored to use `_run_detectors()` directly without writing to `_bars`.

---

## 13. EXACT PA-2 CHANGES REQUIRED

**Target:** `scripts/run_paper_trading.py:284` and `research_platform/live_trading/plugin.py:199` only.

### `run_paper_trading.py` change:
```python
# BEFORE (line 284):
bars_list = pa_orch._bars.get(symbol, [])

# AFTER:
bars_list = pa_orch.get_bars(symbol)
```

### `live_trading/plugin.py` change:
```python
# BEFORE (line 199):
bars_list = pa_orch._bars.get(symbol, [])

# AFTER:
bars_list = pa_orch.get_bars(symbol)
```

**Note:** `live_trading/plugin.py` is an additional `_bars` caller **not previously documented** in earlier gate reports. PA-2 must update **both** callers.

**Do NOT implement PA-2 until PA-1 is complete and tests pass.**

---

## 14. CONTRADICTIONS DISCOVERED

| # | Previous Claim | Source Evidence | Status |
|---|---|---|---|
| C-1 | Previous gate reports listed 2 `_bars` callers (run_paper_trading.py + test file). | Grep confirmed **4 callers total**: `run_paper_trading.py:284`, `live_trading/plugin.py:199`, `test_sprint2_intelligence.py:61`, `test_sprint2_intelligence.py:83`. | ⚠️ **CONTRADICTION** — `live_trading/plugin.py` was missed. PA-2 scope must include it. |
| C-2 | `SessionUpdated` was listed as a published event in the PA architecture. | Source inspection confirms `SessionUpdated` is **defined** in `events.py:20` but **never published** anywhere in `orchestrator.py`. No session detection logic exists. | ⚠️ **CONTRADICTION** — `SessionUpdated` is dead code. No session period detection is implemented. |
| C-3 | Previous plan stated downstream components subscribe to `StructureDetected` / `ImbalanceDetected` via EventBus. | No subscriber to either event was found in any active paper-trading component. | ⚠️ **CONTRADICTION** — Events are published but have no active consumers. |

---

## 15. BLOCKERS

**No hard blockers that prevent PA-1 implementation.**

Documented items to manage:

| # | Item | Severity | Action |
|---|---|---|---|
| B-1 | `live_trading/plugin.py:199` accesses `_bars` directly. This caller was undocumented. | Low | Add to PA-2 scope. |
| B-2 | `SessionUpdated` event is never published. No session detection logic exists. | Low | Document as unimplemented feature. Do not implement in Sprint 003. |
| B-3 | Test `test_price_action_fvg_imbalances()` writes directly to `_bars`. Must be refactored in PA-3. | Low | Refactor in PA-3 to call `_run_detectors()` directly without mutating `_bars`. |

---

## 16. CTO RECOMMENDATION

1. **`SessionUpdated` is dead code.** Do not implement session detection in Sprint 003. Mark as future enhancement.
2. **`live_trading/plugin.py`** must be added to PA-2 scope. It was previously missed. Both production `_bars` callers must be updated together.
3. **Defensive copy in `get_bars()`** is mandatory. Return `list(self._bars.get(symbol, []))` — not a reference to the internal list.
4. **Test refactor:** `test_price_action_fvg_imbalances()` direct `_bars` write must be replaced in PA-3. Suggested approach: call `_run_detectors(symbol)` after populating `_bars` via `process_tick()` ticks, or accept `_run_detectors()` as a semi-internal method exposed for test purposes only.
5. **No EventBus consumers** exist for PA events. This is not a Sprint 003 blocker, but must be documented for Phase 5 (Feature Pipeline) design.

---

## PA-0 GATE CLASSIFICATION

```text
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║   PA-0 DISCOVERY GATE CLASSIFICATION:                                     ║
║   PASS                                                                    ║
║                                                                           ║
║   Source inspection complete. All 22 PA-0 verification items confirmed.   ║
║   3 contradictions discovered and documented (no blockers).               ║
║   0 production Python files modified.                                     ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

---

## EXACT NEXT ACTION

**PA-1 ONLY:**

1. Add `get_bars(self, symbol: str) -> List[Dict[str, Any]]` to `IPriceActionOrchestrator` in `research_platform/price_action/interfaces.py`.
2. Implement `get_bars()` returning `list(self._bars.get(symbol, []))` in `PriceActionOrchestrator` in `research_platform/price_action/orchestrator.py`.
3. Add unit tests verifying: empty-list return for unknown symbol, correct bars after tick ingestion, defensive copy guarantee.
4. Run regression suite to confirm 0 regressions.

**STOP. Do not proceed to PA-2 until PA-1 is complete and CTO approves.**
