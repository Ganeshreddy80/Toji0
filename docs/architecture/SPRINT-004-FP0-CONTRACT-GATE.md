# SPRINT 004 — FP-0 CONTRACT DEFINITION GATE
## Feature Pipeline Integration Contract: Formal Definitions & Architectural Decisions

**Author:** TOJI CTO / Lead Architect  
**Date:** 2026-08-11  
**Governance:** Master Architecture Governance — Sprint 004 / FP-0 Contract Definition  
**Predecessor:** `SPRINT-004-FEATURE-PIPELINE-DISCOVERY-GATE.md` — **CERTIFIED PASS**  
**Stage:** FP-0 — DOCUMENTATION AND CONTRACT DEFINITION ONLY  
**Production Python Files Modified:** 0  
**New Tests Created:** 0  

---

## EXECUTIVE SUMMARY

FP-0 resolves 10 architectural decisions discovered in the Sprint 004 Feature Pipeline Discovery audit. All decisions are formally recorded below with source-level evidence, semantic analysis, rejected alternatives, and consequences. No production code is modified in this stage.

The FP-0 gate produces:
- A canonical Feature Ownership Matrix (20 features)
- ATR canonical source decision (ADR-001)
- Volatility contract definition (partially resolved, one open question remains)
- StrategyLoop `extract_features()` resolution
- Feature Store lifecycle definition
- EventBus role classification
- Determinism contract
- Ordered FP-1 through FP-6 implementation sequence

---

## SECTION 1 — FEATURE OWNERSHIP MATRIX

This is the authoritative table of all features currently present in the system.

### 1.1 Canonical Feature Definitions

| # | Name | Canonical Owner | Transformer Class | Formula / Algorithm | Parameters | Input Columns | Consumers | Duplicate Implementations |
|---|---|---|---|---|---|---|---|---|
| 1 | `close` | Feature Platform | `CloseTransformer` | Identity: `df["close"]` | — | `close` | `ai_signal`, `exit_engine`, `trade_journal` | None |
| 2 | `open` | Feature Platform | `OpenTransformer` | Identity: `df["open"]` | — | `open` | `run_paper_trading`, `live_trading/plugin` | None |
| 3 | `high` | Feature Platform | `HighTransformer` | Identity: `df["high"]` | — | `high` | `run_paper_trading`, `live_trading/plugin` | None |
| 4 | `low` | Feature Platform | `LowTransformer` | Identity: `df["low"]` | — | `low` | `run_paper_trading`, `live_trading/plugin` | None |
| 5 | `volume` | Feature Platform | `VolumeTransformer` | Identity: `df["volume"]` | — | `volume` | `run_paper_trading`, `live_trading/plugin` | None |
| 6 | `log_return` | Feature Platform | `LogReturnTransformer` | `log(close_t / close_{t-1})`, fillna 0.0 | — | `close` | `rolling_std` (indirect) | None |
| 7 | `rolling_std` | Feature Platform | `RollingStdTransformer` | `rolling(20).std(log_return)`, fillna 0.0 | window=20 | `log_return` | Intermediate only (upstream of signal chain) | None |
| 8 | `atr` | **CONTESTED** | `AtrTransformer` (FP) + `_calculate_atr` (PA) | See Section 2 | window=14 | `high`, `low`, `close` | `ai_signal`, `exit_engine`, `trade_journal`, `confluence`, strategy | **YES — two implementations** |
| 9 | `normalized_atr` | Feature Platform | `NormalizedAtrTransformer` | `atr / (close + 1e-10)`, fillna 0.0 | — | `atr`, `close` | `exit_engine` | None |
| 10 | `risk_score` | Feature Platform | `RiskScoreTransformer` | z-score of `normalized_atr` over 50-bar window: `(normalized_atr - rolling_mean) / (rolling_std + 1e-10)`, fillna 0.0 | window=50 | `normalized_atr` | `exit_engine` (via `query_latest`) | None |
| 11 | `signal` | Feature Platform | `SignalTransformer` | `1.0 if abs(risk_score) > 2.0 else 0.0` | threshold=2.0 | `risk_score` | Not directly queried by production callers | None |
| 12 | `ema9` | Feature Platform | `EmaTransformer(9)` | `ewm(span=9, adjust=False).mean()`, fillna from `close` | span=9 | `close` | `ai_signal`, `trade_journal`, `run_paper_trading` | None |
| 13 | `ema21` | Feature Platform | `EmaTransformer(21)` | `ewm(span=21, adjust=False).mean()`, fillna from `close` | span=21 | `close` | `ai_signal`, `trade_journal`, `run_paper_trading` | None |
| 14 | `ema50` | Feature Platform | `EmaTransformer(50)` | `ewm(span=50, adjust=False).mean()`, fillna from `close` | span=50 | `close` | `ai_signal`, `trade_journal`, `run_paper_trading` | None |
| 15 | `rsi` | Feature Platform | `RsiTransformer` | Standard RSI(14): `100 - (100 / (1 + (avg_gain / (avg_loss + 1e-10))))`, fillna 50.0 | window=14 | `close` | `ai_signal`, `trade_journal`, `run_paper_trading` | None |
| 16 | `volume_change` | Feature Platform | `VolumeChangeTransformer` | `volume.pct_change()`, fillna 0.0 | — | `volume` | `ai_signal`, `trade_journal` | None |
| 17 | `support` | Feature Platform | `SupportTransformer` | `low.rolling(20).min()`, fillna from `low` | window=20 | `low` | `ai_signal`, `trade_journal`, `run_paper_trading` | None |
| 18 | `resistance` | Feature Platform | `ResistanceTransformer` | `high.rolling(20).max()`, fillna from `high` | window=20 | `high` | `ai_signal`, `trade_journal`, `run_paper_trading` | None |
| 19 | `breakout` | Feature Platform | `BreakoutTransformer` | `"breakout_high"` if `close > prev_resistance`; `"breakout_low"` if `close < prev_support`; else `"none"` | — | `close`, `resistance`, `support` | `ai_signal`, `trade_journal` | None |
| 20 | `trend` | Feature Platform | `TrendDirectionTransformer` | `"bullish"` if `ema9 >= ema21` else `"bearish"` | — | `ema9`, `ema21` | `ai_signal`, `trade_journal`, `run_paper_trading` | None |

**Features queried but NOT in pipeline:** `volatility` (see Section 3).  
**Features implemented but NOT queried by any production caller:** `rolling_std`, `log_return`, `signal`.

### 1.2 Additional Price Action State (Not Feature Platform)

These are produced by `PriceActionOrchestrator` and served via its own public API. They are NOT stored in `FeatureStore`.

| State | PA Method | Consumer |
|---|---|---|
| ATR (float) | `get_atr(symbol)` | `ai_signal`, `confluence`, `run_paper_trading`, strategy |
| VWAP (float) | `get_vwap(symbol)` | `confluence`, `run_paper_trading`, strategy |
| Swing points | `get_swings(symbol)` | `confluence` |
| BOS/CHOCH | `get_structure_changes(symbol)` | `confluence` |
| Order blocks | `get_blocks(symbol)` | `confluence` |
| FVG gaps | `get_gaps(symbol)` | `confluence` |
| 1m OHLCV bars | `get_bars(symbol)` | `run_paper_trading`, `live_trading`, `backend/main.py`, E2E tests |

---

## SECTION 2 — ATR DECISION (ADR-001)

### 2.1 Implementation A — Price Action ATR (`pa_orch.get_atr()`)

**Location:** `research_platform/price_action/orchestrator.py`, lines 227–242  
**Trigger:** Called at the end of `_run_detectors()` which fires every time a new bar closes (i.e., once per bar boundary crossing).  
**Algorithm:**

```python
tr_list = []
for i in range(1, len(bars)):
    high = bars[i]["high"]
    low  = bars[i]["low"]
    prev_close = bars[i - 1]["close"]
    tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
    tr_list.append(tr)

atr = sum(tr_list[-14:]) / min(len(tr_list), 14)
```

**Characteristics:**
- Simple Moving Average (SMA) of True Range over the last 14 bars
- Recomputed from the full bar list on every bar close
- Stored as a single float per symbol in `self._atr[symbol]`
- Available immediately after the 2nd bar closes (no minimum period beyond 2 bars)
- Returns 0.0 before first computation
- Operates on up to the last 200 bars (bounded by PA bar cap)
- Updated at bar-close frequency, not tick frequency

### 2.2 Implementation B — Feature Platform ATR (`FeaturePipeline.AtrTransformer`)

**Location:** `research_platform/feature_platform/transformers.py`, lines 44–64  
**Trigger:** Called during `compute_and_store()` which is called per-tick from the tick handler.  
**Algorithm:**

```python
high = df["high"]
low  = df["low"]
close_prev = df["close"].shift(1)

tr1 = high - low
tr2 = (high - close_prev).abs()
tr3 = (low  - close_prev).abs()

tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
atr = tr.rolling(window=14).mean()
atr = atr.fillna(0.0)
```

**Characteristics:**
- Rolling Mean (equivalent to SMA) of True Range over 14-bar window using pandas `rolling().mean()`
- Produces a full Series across all input rows (vector computation)
- Latest value (last row) is the effective "current" ATR
- Returns 0.0 for the first 13 rows (fillna)
- Operates on whatever bar DataFrame is passed to `compute_and_store()`
- The input DataFrame may have fewer or more than 14 rows depending on caller

### 2.3 Numerical Equivalence Analysis

Both implementations compute **SMA of True Range over 14 bars**.

**Identity conditions (numerically equivalent when):**
- The input bar data to FP-ATR is identical to the bar data held in `pa_orch._bars[symbol]`
- The number of bars passed to FP-ATR is ≥ 14
- Both are evaluated at the same bar-close point in time

**Divergence conditions (may differ when):**
1. FP-ATR receives a DataFrame with fewer than 14 bars → returns 0.0 for recent rows; PA-ATR returns a partial SMA from available bars (no minimum bar count beyond 2)
2. PA-ATR uses `self._bars` (up to 200 bars, windowed SMA over last 14); FP-ATR uses `rolling(14).mean()` over the entire passed DataFrame — if the DataFrame has N > 14 rows, the last rolling value is identical to PA's `sum(tr_list[-14:]) / 14` only when both operate on the same 14 bars
3. PA-ATR is computed at bar-close (via `_run_detectors`). FP-ATR is computed during `compute_and_store()` which is called per-tick. Between bar-close events, the tick handler calls `compute_and_store()` with bars where the last bar's OHLC may still be an in-progress bar. PA-ATR includes only closed bars in its SMA.

**Conclusion:** The two implementations are mathematically equivalent (SMA-ATR-14) but may differ in value at any given moment due to (3) above — the FP-ATR may incorporate an open/partial bar that PA-ATR excludes. In practice, `close` and `high`/`low` of the current open bar evolve tick-by-tick, making FP-ATR non-stable between bar boundaries.

### 2.4 Decision (ADR-001): Canonical ATR Source

**DECISION: `pa_orch.get_atr(symbol)` is the canonical ATR for all strategy and risk consumption.**

**Rationale:**
1. PA-ATR is computed only at bar-close boundaries — it is stable between bar closes, making it suitable for strategy decisions and stop-loss/take-profit computation.
2. PA-ATR is part of the Sprint 003-certified `IPriceActionOrchestrator` public contract.
3. `ai_signal/signal_generator.py` already uses `pa_orch.get_atr()` directly and correctly (line 26).
4. `confluence/scoring_engine.py` uses `pa_orch.get_atr()` directly and correctly (line 31).
5. FP-ATR exists in the Feature Store for the purpose of feeding `normalized_atr` and `risk_score` in the Feature Pipeline DAG — it is an internal intermediate computation, not the primary ATR signal.

**Rejected alternative:** Making FP-ATR the canonical source would require all callers to issue `store.query_latest()` calls (slower, storage-dependent) instead of a direct in-memory lookup, and would introduce the partial-bar instability issue into strategy decisions.

**Consequences:**
- `FeaturePipeline.AtrTransformer` remains valid as an internal intermediate only (feeding `normalized_atr`).
- `exit_engine/orchestrator.py` currently queries `store.query_latest(["atr", ...])` (FP-ATR). This is a **divergence from the canonical source** to be resolved in FP-4.
- `trade_journal` queries `store.query_latest(["atr", ...])` — same divergence, same resolution path.
- No production code changes in FP-0.

**Migration boundary:** FP-ATR internal usage (feeding `normalized_atr → risk_score`) is authorized. External consumers of `atr` values for strategy/risk decisions must use `pa_orch.get_atr()`.

---

## SECTION 3 — VOLATILITY CONTRACT

### 3.1 Source Evidence

Two callers query `"volatility"` from the Feature Store:

**Caller A:** `position_sizing/orchestrator.py`, method `calculate_size()`, sizing method `"volatility"`:
```python
# Volatility target: target_volatility / asset_volatility
# Check FeatureStore for volatility if available, else default to 0.02 (2% daily)
vol = 0.02  # hard-coded fallback
if self._container.has("FeaturePlatformOrchestrator"):
    store = self._container.resolve("FeaturePlatformOrchestrator").store
    df = store.query_latest(["volatility"], [symbol])
    if df is not None and not df.empty and "volatility" in df.columns:
        vol = float(df.iloc[0]["volatility"])
target_capital = equity * (self._config.target_volatility / max(vol, 0.001))
raw_qty = target_capital / price
```

**Caller B:** `position_sizing/orchestrator.py`, method `calculate_size()`, sizing method `"risk_parity"`:
```python
vol = 0.02  # hard-coded fallback
if self._container.has("FeaturePlatformOrchestrator"):
    store = self._container.resolve("FeaturePlatformOrchestrator").store
    df = store.query_latest(["volatility"], [symbol])
    if df is not None and not df.empty and "volatility" in df.columns:
        vol = float(df.iloc[0]["volatility"])
vols_dict = {symbol: vol, "baseline": 0.02}
weights = self._risk_parity.calculate_weights(vols_dict)
```

**Default fallback:** `vol = 0.02` (2% daily volatility) in both cases.

### 3.2 Semantic Analysis

The code comments state: **"Volatility target: target_volatility / asset_volatility"** and uses `target_volatility` (from env `TARGET_VOLATILITY`, default `0.10` = 10%).

The formula `equity * (target_volatility / max(vol, 0.001))` is consistent with **volatility targeting**, a standard portfolio sizing technique where position size is inversely proportional to realized volatility. In this context, `volatility` is expected to be a **daily percentage volatility** (dimensionless, e.g., 0.02 = 2%).

### 3.3 Comparison with Existing Feature Platform Outputs

| Feature | Description | Dimensionality | Appropriate as `volatility`? |
|---|---|---|---|
| `atr` | Average True Range (absolute price units, e.g., $340 for BTC) | Absolute price delta | ❌ No — wrong units |
| `normalized_atr` | `atr / close` (dimensionless ratio, e.g., 0.007 = 0.7%) | Dimensionless ratio of ATR to price | ✅ **Semantically closest** — approximates percentage ATR |
| `risk_score` | Z-score of `normalized_atr` over 50 bars | Dimensionless z-score (negative/positive, unbounded) | ❌ No — wrong semantics, not a volatility measure |
| `rolling_std` | Rolling std of `log_return` (20-bar window) | Dimensionless std of log returns | ✅ **Semantically equivalent** — standard definition of realized volatility |

### 3.4 Resolution

**`normalized_atr` is semantically closest to "percentage volatility" currently available** in the Feature Store. It equals `ATR / close`, which is a common proxy for percentage daily range. For a symbol like BTCUSDT at $65,000 with ATR $340, `normalized_atr ≈ 0.0052` (0.52%).

**`rolling_std` of `log_return`** is the classical finance definition of realized volatility. It is computed over 20 bars of 1-minute log returns, which represents 20-minute realized volatility — not daily volatility. If converted to a daily basis, it would require scaling by `sqrt(1440 / 20)`.

### 3.5 Open Question — UNRESOLVED

> **OQ-1:** What volatility measure did the position sizing designer intend? The fallback default of `0.02` (2% daily) is consistent with daily percent volatility. `normalized_atr` (which exists) approximates this as percentage ATR. `rolling_std` (which exists) approximates this as 20-minute realized vol (not daily).
>
> **Evidence is insufficient to determine** whether `normalized_atr` or `rolling_std` is the intended `volatility` feature without the original designer's specification.
>
> **Resolution required:** CTO must decide whether `volatility` should map to `normalized_atr` (ATR-based percentage), `rolling_std` scaled to daily (returns-based), or a new dedicated `daily_vol` transformer.

**Current behavior:** Both callers safely fall back to `vol = 0.02` when `"volatility"` is absent from the store. The system is operationally safe — position sizing using `"volatility"` or `"risk_parity"` methods silently defaults. This is a known gap, not a crash.

**Decision deferred:** FP-3 implementation cannot begin until OQ-1 is resolved by CTO.

---

## SECTION 4 — STRATEGY LOOP CONTRACT

### 4.1 Source Trace

**The call site:**
```python
# research_platform/runtime/strategy_loop.py, lines 23–28
feature_store = self.container.resolve("FeaturePlatformOrchestrator")
if feature_store and hasattr(feature_store, "extract_features"):
    context["features"] = feature_store.extract_features()
```

**Analysis:**
1. The container resolves `"FeaturePlatformOrchestrator"` — which is `FeaturePlatformOrchestrator` (the institutional Feature Platform).
2. `hasattr(feature_store, "extract_features")` evaluates to **False** — `FeaturePlatformOrchestrator` does not have an `extract_features()` method.
3. Therefore `context["features"]` is **never populated** via this path.
4. The `except Exception: pass` block ensures this failure is entirely silent.

**What `extract_features()` does exist on:** `research_platform/research_lab/feature_store.py`, `research_lab/orchestrator.py`. These are entirely separate research_lab components (not the Feature Platform) with a signature `extract_features(name: str, data: List[float]) → FeatureData` that computes simple price differences from a list. This is a **wholly different API** — not compatible with the Feature Platform's `FeaturePlatformOrchestrator`.

### 4.2 Root Cause

The `StrategyLoop` was written to interface with `research_platform/research_lab/` (the older research lab feature store), then later the DI container was updated to register `FeaturePlatformOrchestrator` under the key `"FeaturePlatformOrchestrator"`, creating a namespace collision between two distinct subsystems.

The `hasattr` guard was added as a safety net but effectively made the whole block dead code — it never executes in the current architecture.

### 4.3 What StrategyLoop Actually Needs

From the code context, `StrategyLoop.execute()` puts `context["features"]` which is then passed downstream. The downstream `evaluate_signals()` call on `StrategyLabOrchestrator` receives `context.get("tickers", {})` not `context.get("features", {})`, so even if features were populated, they are currently unused by `StrategyLabOrchestrator.evaluate_signals()`.

**Conclusion:** `StrategyLoop` does not presently require any feature data to function correctly in its current implementation. The `context["features"]` path is dead code.

### 4.4 Mapping to Existing Feature Platform API

If `StrategyLoop` is to be given access to latest computed features for signal evaluation, the correct mapping is:

| Intent | Correct API |
|---|---|
| Get latest computed features for a symbol | `FeaturePlatformOrchestrator.query_realtime(names, symbols)` → `pd.DataFrame` |
| Get the last computed row | `df.iloc[-1].to_dict()` |
| Get list of all registered features | `FeaturePlatformOrchestrator.registry.list_all()` |

**No new method needs to be created.** `query_realtime()` already exists and is the correct interface.

**No production code changes in FP-0.** The broken `extract_features()` call remains in place until FP-2 authorization.

---

## SECTION 5 — FEATURE STORE LIFECYCLE DEFINITION

### 5.1 Current Design — Observed Behavior

`FeatureStore` (`research_platform/feature_platform/feature_store.py`) maintains two internal dictionaries:

```python
_offline_db: Dict[Tuple[str, str, str], pd.DataFrame]  # (name, version, symbol) → full history df
_online_db:  Dict[Tuple[str, str, str], pd.DataFrame]  # (name, version, symbol) → latest 1-row df
```

**Offline store** (`_offline_db`): stores the complete output DataFrame from every `compute_and_store()` call. This grows with every invocation. For 15 features × N ticks per session, each containing up to 200 bars, the offline store grows unboundedly.

**Online store** (`_online_db`): stores only the most recent 1-row slice (`tail(1)`) for each `(name, version, symbol)` key. This is O(constant) per key — it does not grow with time.

**Eviction policy:** None. No eviction, TTL, or size bound exists in either store.

### 5.2 Intended Responsibilities

Based on source evidence:

| Store | Intended Use | Who Uses It |
|---|---|---|
| `_online_db` / `query_latest()` | Real-time/live feature retrieval for strategy, risk, signal decisions | `ai_signal`, `exit_engine`, `position_sizing`, `trade_journal` |
| `_offline_db` / `query_historical()` | Historical PIT time-travel backtesting/research queries | No production caller currently |

### 5.3 Retention Requirements (Defined in FP-0)

**Online Store:**
- **Requirement:** Retain the last computed value per feature per symbol. O(1) growth per key.
- **Current behavior:** Correct. `tail(1)` semantics are appropriate.
- **Retention:** Indefinite within a session (last value); reset on restart. This is acceptable for live/paper trading.

**Offline Store:**
- **Requirement:** Not consumed by any production path today. Growth is unbounded and unchecked.
- **Risk:** In a 10-symbol session at 1 tick/second over 8 hours = ~28,800 ticks, each `compute_and_store()` writes a DataFrame of up to 200 bars × 15 features. At ~28,800 calls/session, the offline store accumulates up to 28,800 DataFrame copies per feature per symbol.
- **Decision:** The offline store is not intentionally unbounded — the design includes PIT semantics for backtesting, but no retention policy was specified.

**FP-0 Retention Contract:**
- Online store: retain last-1 per (name, version, symbol). **No change required.**
- Offline store: **Retention policy is UNDEFINED and must be specified in FP-5 before implementing any eviction.** For FP-1 through FP-4, the offline store unbounded growth is an accepted known risk within single-session operation. It is NOT implemented as eviction in FP-0.

### 5.4 Persistence Classification

| Layer | Persistence | Notes |
|---|---|---|
| `FeatureStore` | In-memory only | All data lost on restart |
| `FeatureRegistry` | In-memory only | All registrations lost on restart |
| `FeatureRepository` | In-memory only | All records lost on restart |
| All governance repos | In-memory only | All approval/version history lost on restart |
| `PriceActionRepository` | In-memory only | All swings/gaps/blocks lost on restart |

**Contract established in FP-0:** All Feature Platform and Price Action state is session-scoped. No persistence guarantee exists across restarts. Any future persistence layer must be explicitly authorized as a separate sprint.

---

## SECTION 6 — EVENTBUS ROLE CLASSIFICATION

### 6.1 Classification Decision

Based on source evidence (zero subscribers in any production module):

#### Price Action Events

| Event | Classification | Rationale |
|---|---|---|
| `StructureDetected` | **(c) Audit/Observability** | Published 4 sites per bar close; zero subscribers; no production code acts on it. Current role: passive audit trail via `InMemoryEventBus.get_timeline()`. |
| `ImbalanceDetected` | **(c) Audit/Observability** | Published on FVG detection; zero subscribers; same audit role. |
| `SessionUpdated` | **(c) Audit/Observability** (stub) | Defined and imported but **never published** by Price Action. Cannot be classified as any active role. |

#### Feature Platform Events

| Event Class | Classification | Rationale |
|---|---|---|
| `FeatureRegistered`, `FeatureValidated`, `FeatureCalculated`, `FeatureRejected` | **(c) Audit/Observability** | Published per compute cycle; no production subscriber acts on them. |
| `FeaturePromoted`, `FeatureFreshnessUpdated`, `FeatureImportanceCalculated`, `FeatureVersionCreated` | **(c) Audit/Observability** | Governance events; published by methods that are themselves never called from production paths. |

### 6.2 Formal Classification

**FP-0 Decision:** All EventBus events in both `research_platform/price_action/events.py` and `research_platform/feature_platform/events.py` are **classified as (c) Audit/Observability signals** in their current state.

This classification is based on observed behavior only and does not foreclose future evolution. Specifically:

- `StructureDetected` and `ImbalanceDetected` **could** become **(b) Asynchronous Integration Events** if a future sprint authorizes wiring a Feature Pipeline subscriber to recompute on regime shift.
- They are NOT **(a) Synchronous Computation Triggers** because the Feature Pipeline computation is currently synchronous and inline (called directly per-tick, not via event subscription).

### 6.3 Preserved Current Behavior

No EventBus subscription wiring is introduced in FP-0 through FP-4. The classification above is a formal statement of what the events are today. Any change from (c) to (a) or (b) requires explicit CTO authorization as a separate architectural decision.

---

## SECTION 7 — DETERMINISM CONTRACT

### 7.1 Required Deterministic Inputs

The Feature Pipeline is deterministic if and only if:

1. **The input DataFrame is deterministic.** The input is `pd.DataFrame(pa_orch.get_bars(symbol))`. Since `get_bars()` returns a defensive copy, and PA is Sprint 003-certified deterministic, the input is deterministic for a given tick sequence.

2. **All transformers are stateless pure functions.** All 20 current transformers are stateless. Given identical input DataFrames, all transformers produce identical output Series. ✅ Verified by source inspection.

3. **The `as_of` timestamp does not affect feature values.** The `as_of` field is metadata only — it is appended to the DataFrame after computation and does not influence any transformer. ✅ Verified.

4. **The validator does not modify computed values.** `FeatureValidator.validate()` is read-only — it inspects but does not mutate the DataFrame. ✅ Verified.

### 7.2 Non-Deterministic Components (Identified)

| Source | Non-Determinism | Impact on Feature Values |
|---|---|---|
| `compute_and_store()` line 166: `as_of = as_of_time or datetime.now(timezone.utc)` | Wall-clock timestamp inserted as `as_of` | **No impact on feature values.** `as_of` is metadata only. Does not affect transformer outputs. |
| `compute_and_store()` line 173: `output_df["effective_time"] = datetime.now(timezone.utc)` | Wall-clock timestamp when `timestamp` column is absent | **No impact on feature values.** Metadata only. |
| `FeatureRecord` fields `created_time`, `updated_time` | `datetime.utcnow()` at registration | **No impact on feature values.** Registration metadata only. |

**Conclusion:** The Feature Pipeline is **functionally deterministic** — for identical input bar DataFrames, all computed feature values are bit-for-bit identical. The non-deterministic components are metadata fields only.

### 7.3 Reference-Time Semantics (Contract)

**Formal definition established in FP-0:**

- `effective_time` of a feature row = the `timestamp` of the bar from which it was computed. If `timestamp` is absent from the input, it defaults to `datetime.now()` — this is a metadata degradation, not a feature value error.
- `as_of` = the wall-clock time at which `compute_and_store()` was invoked. This represents the "observation timestamp" for PIT queries.
- For determinism validation (analogous to PA-4), the reference time shall be injected via the existing `as_of_time: Optional[datetime]` parameter of `compute_and_store()`. **This parameter already exists and is already the correct contract.** No code change required — callers just need to use it.

**FP-5 Determinism Validation:** The Feature Pipeline determinism test (analogous to PA-4) shall pass `as_of_time=datetime(2026, 1, 1, tzinfo=timezone.utc)` to both orchestrator instances to ensure identical `as_of` metadata, enabling byte-identical DataFrame comparison.

---

## SECTION 8 — FEATURE CONTRACT MATRIX (CANONICAL)

This is the authoritative single-source contract table for all features. All future FP stages must be consistent with this matrix.

### 8.1 Production Feature Set (15 computed, registered per-tick today)

| Feature | Type | Input | Warmup Bars | Output Type | FP Transformer | PA Equivalent | Store Persisted |
|---|---|---|---|---|---|---|---|
| `open` | Raw OHLCV | `open` col | 0 | float | `OpenTransformer` | None | Online + Offline |
| `high` | Raw OHLCV | `high` col | 0 | float | `HighTransformer` | None | Online + Offline |
| `low` | Raw OHLCV | `low` col | 0 | float | `LowTransformer` | None | Online + Offline |
| `close` | Raw OHLCV | `close` col | 0 | float | `CloseTransformer` | None | Online + Offline |
| `volume` | Raw OHLCV | `volume` col | 0 | float | `VolumeTransformer` | None | Online + Offline |
| `ema9` | Indicator | `close` | 0 (fills from close) | float | `EmaTransformer(9)` | None | Online + Offline |
| `ema21` | Indicator | `close` | 0 (fills from close) | float | `EmaTransformer(21)` | None | Online + Offline |
| `ema50` | Indicator | `close` | 0 (fills from close) | float | `EmaTransformer(50)` | None | Online + Offline |
| `rsi` | Indicator | `close` | 14 (fills 50.0) | float [0–100] | `RsiTransformer(14)` | None | Online + Offline |
| `atr` | Indicator (Internal) | `high`, `low`, `close` | 14 (fills 0.0) | float (abs) | `AtrTransformer(14)` | `get_atr()` (canonical) | Online + Offline |
| `volume_change` | Indicator | `volume` | 1 (fills 0.0) | float | `VolumeChangeTransformer` | None | Online + Offline |
| `support` | Level | `low` | 20 (fills from low) | float | `SupportTransformer(20)` | `get_gaps()` (different concept) | Online + Offline |
| `resistance` | Level | `high` | 20 (fills from high) | float | `ResistanceTransformer(20)` | `get_gaps()` (different concept) | Online + Offline |
| `breakout` | Signal | `close`, `resistance`, `support` | 0 | string enum: `"breakout_high"`, `"breakout_low"`, `"none"` | `BreakoutTransformer` | None | Online + Offline |
| `trend` | Signal | `ema9`, `ema21` | 0 | string enum: `"bullish"`, `"bearish"` | `TrendDirectionTransformer` | `_trend` (internal) | Online + Offline |

### 8.2 Internal DAG-Only Features (registered per-tick but not directly queried by production callers)

| Feature | Type | Warmup | Purpose |
|---|---|---|---|
| `log_return` | Intermediate | 1 | Feeds `rolling_std` |
| `rolling_std` | Intermediate | 20 | Feeds `signal` chain; not directly consumed |
| `normalized_atr` | Intermediate | 14 | Feeds `risk_score`; queried by `exit_engine` |
| `risk_score` | Risk Metric | 50 | Queried by `exit_engine` |
| `signal` | Threshold | 50 | Not queried by any production caller today |

### 8.3 Queried But Not Implemented

| Feature | Queried By | Status |
|---|---|---|
| `volatility` | `position_sizing` (methods: `"volatility"`, `"risk_parity"`) | ❌ NOT in pipeline registry. Safe fallback to `0.02` exists. |

---

## SECTION 9 — ARCHITECTURAL DECISION RECORDS

### ADR-001: Canonical ATR Source
**Status:** DECIDED  
**Context:** Two independent ATR implementations produce the same algorithm (SMA-ATR-14) but at different frequencies and with different bar-boundary semantics.  
**Decision:** `pa_orch.get_atr(symbol)` is the canonical external ATR for strategy, risk, and signal decisions. FP `AtrTransformer` output remains internal to the Feature Pipeline DAG only (feeding `normalized_atr`).  
**Evidence:** PA-ATR is stable between bar closes; FP-ATR may reflect partial open bars. PA-ATR is on certified public interface.  
**Rejected:** Making FP-ATR canonical (introduces partial-bar instability, store-access overhead, regression on certified interface).  
**Consequence:** `exit_engine` and `trade_journal` currently use FP-ATR via `store.query_latest(["atr"])`. These are boundary violations to be corrected in FP-4.

---

### ADR-002: `StrategyLoop.extract_features()` Is Dead Code
**Status:** DECIDED  
**Context:** `StrategyLoop` resolves `"FeaturePlatformOrchestrator"` and calls `.extract_features()` which does not exist on that object.  
**Decision:** The call block is formally classified as **dead code**. `context["features"]` is never populated by this path. Downstream `StrategyLabOrchestrator.evaluate_signals()` does not use `context["features"]`, so no functional regression exists.  
**Evidence:** `hasattr(feature_store, "extract_features")` evaluates to `False` for `FeaturePlatformOrchestrator`. The silent `try/except` block masks the dead code completely.  
**Correct Mapping:** `query_realtime(names, symbols)` is the correct replacement API.  
**Action:** FP-2 — fix `StrategyLoop` to use `query_realtime()`. No change in FP-0.

---

### ADR-003: EventBus Events Are Audit/Observability Only
**Status:** DECIDED  
**Context:** `StructureDetected`, `ImbalanceDetected`, and all Feature Platform events are published with zero subscribers.  
**Decision:** All events classified as **(c) Audit/Observability** for Sprint 004 scope. The `InMemoryEventBus.get_timeline()` serves as the consumption point (as used by `backend/main.py` `/api/v1/signals` endpoint).  
**Evidence:** No subscribe() call found for any of these events in any production module.  
**Consequence:** Feature computation remains synchronous/polling (called per-tick inline). Event-driven computation is a future architectural option, not a Sprint 004 requirement.

---

### ADR-004: Feature Registration Is One-Time-Per-Session, Not Per-Tick
**Status:** DECIDED (implementation deferred to FP-1)  
**Context:** `register_feature()` is called on every tick (15 × every tick), suppressing `ValueError` silently.  
**Decision:** Feature registration must occur once at container startup / `FeaturePlatformPlugin.initialize()`, not per-tick. Per-tick registration is architecturally incorrect.  
**Evidence:** `FeatureRegistry.register()` explicitly raises `ValueError` on duplicate. The suppression is an implicit idempotency hack.  
**Action:** FP-1 — create `FeatureBootstrap` utility or extend `FeaturePlatformPlugin.initialize()` to register all production features.

---

### ADR-005: `store.query_latest()` vs `query_realtime()` — Direct Access Is a Boundary Violation
**Status:** DECIDED (resolution deferred to FP-2)  
**Context:** Production callers access `feature_platform.store.query_latest()` directly instead of `feature_platform.query_realtime()`.  
**Decision:** `query_realtime()` is the authoritative public API. Direct `.store` access bypasses the orchestrator boundary.  
**Evidence:** `query_realtime()` exists (line 219, `orchestrator.py`) and delegates directly to `store.query_latest()`. The public interface exists; callers are not using it.  
**Action:** FP-2 — update all callers: `ai_signal`, `exit_engine`, `position_sizing`, `trade_journal`. No production code change in FP-0.

---

### ADR-006: FeatureStore Offline Store Retention Is Undefined
**Status:** DECIDED (policy definition deferred to FP-5)  
**Context:** `_offline_db` grows unboundedly — a new DataFrame copy is written per `compute_and_store()` call.  
**Decision:** The offline store retention policy is formally **undefined** and must be specified as part of FP-5 (determinism validation stage). No eviction implementation is authorized until the policy is defined.  
**Evidence:** No eviction code exists in `FeatureStore`. `_online_db` correctly maintains O(1) per key.  
**Consequence:** Within single trading sessions (8-hour runs), the risk is accepted as a known bounded issue. The offline store is not used by any production consumer today.

---

### ADR-007: Feature Platform Determinism Is Functionally Confirmed, Metadata Is Non-Deterministic
**Status:** DECIDED  
**Context:** `datetime.now()` is used for `as_of` and `effective_time` when not injected.  
**Decision:** Feature Pipeline is **functionally deterministic** (feature values). `as_of` and `effective_time` are metadata-only and non-deterministic by wall clock. The `as_of_time: Optional[datetime]` parameter in `compute_and_store()` is the **correct contract for deterministic replay** — it already exists and does not require code changes.  
**Evidence:** All 20 transformers are stateless pure functions. Validator is read-only. Metadata fields don't affect transformer outputs.  
**Action:** FP-5 — determinism test must inject `as_of_time` explicitly.

---

### ADR-008: `volatility` Feature Is Undefined — Fallback Behavior Is Safe
**Status:** PARTIALLY DECIDED — OQ-1 remains open  
**Decided portion:** The system is operationally safe — both sizing methods silently default to `vol = 0.02` when `"volatility"` is absent. This default is reasonable (2% daily volatility is a common market assumption).  
**Undecided:** Whether `volatility` should be `normalized_atr`, `rolling_std` (scaled), or a new transformer.  
**Action:** OQ-1 must be resolved by CTO before FP-3 implementation.

---

### ADR-009: `SessionUpdated` Is a Stub — No Session Boundary Detection Exists
**Status:** DECIDED  
**Context:** `SessionUpdated` is imported in `PriceActionOrchestrator` but never published. No session boundary detection (London/NY/Asia) is implemented.  
**Decision:** `SessionUpdated` is formally classified as a **stub event** pending a future session boundary detection sprint. It is not part of Sprint 004 scope.  
**Evidence:** No `SessionUpdated` publication site exists in `research_platform/price_action/orchestrator.py`. No tick-to-session mapping logic exists.  
**Consequence:** Sprint 004 (FP-1 through FP-6) does not implement session detection. The event stub remains in place.

---

### ADR-010: Duplicate `BreakOfStructureDetected` / `StructureDetected` Are Parallel Non-Integrated Systems
**Status:** DECIDED  
**Context:** `market_intelligence/` and `research_platform/price_action/` have separate structure detection stacks.  
**Decision:** These are declared as **separate domain implementations** with no current integration requirement. No consolidation is authorized in Sprint 004. They remain parallel.  
**Consequence:** No change.

---

## SECTION 10 — IMPLEMENTATION ORDER: FP-1 THROUGH FP-6

### 10.1 Ordered Sequence

```
FP-0  CONTRACT DEFINITION           ← This document. CURRENT STAGE.
  │
FP-1  FEATURE REGISTRATION LIFECYCLE
  │   • Create FeatureBootstrap or extend FeaturePlatformPlugin.initialize()
  │   • Register all 15 production features once at startup
  │   • Remove per-tick register_feature() calls from run_paper_trading.py
  │     and live_trading/plugin.py
  │   • Add idempotent register_if_absent() to orchestrator (optional)
  │   • Gate: confirm features registered once; tick handler no longer registers
  │
FP-2  PUBLIC API BOUNDARY ENFORCEMENT
  │   • Route all store.query_latest() callers → query_realtime()
  │     Affected: ai_signal, exit_engine, position_sizing, trade_journal
  │   • Fix StrategyLoop.extract_features() → query_realtime()
  │   • Gate: no direct .store access in production callers
  │
FP-3  VOLATILITY FEATURE DEFINITION AND IMPLEMENTATION
  │   • BLOCKED ON OQ-1 (CTO decision on volatility semantics)
  │   • After OQ-1 resolved: add correct transformer and register
  │   • Gate: position_sizing.calculate_size("volatility") reads non-default vol
  │
FP-4  ATR CANONICAL SOURCE MIGRATION
  │   • Update exit_engine and trade_journal to use pa_orch.get_atr()
  │     instead of store.query_latest(["atr"])
  │   • FP-ATR remains internal to pipeline DAG (feeds normalized_atr)
  │   • Gate: no external consumer queries Feature Store for "atr" as canonical
  │
FP-5  FEATURE PIPELINE DETERMINISM VALIDATION
  │   • Build replay test comparable to PA-4
  │   • Inject as_of_time in compute_and_store() calls
  │   • Define offline store retention policy
  │   • Gate: two identical tick sequences produce identical feature DataFrames
  │
FP-6  FEATURE PIPELINE PERFORMANCE BASELINE
      • Measure compute_and_store() latency: p50, p95, p99, max
      • Measure per-tick overhead introduced by feature computation
      • Profile pd.DataFrame(bars_list) construction cost
      • Gate: document baseline; no production regression vs PA-5 baseline
```

### 10.2 Dependencies

```
FP-1 → no dependencies (can start immediately)
FP-2 → depends on FP-1 (registration must be stable before routing queries)
FP-3 → depends on OQ-1 resolution (BLOCKED)
FP-4 → depends on FP-2 (public API must be routed before ATR migration)
FP-5 → depends on FP-1, FP-2 (stable registration and API before testing)
FP-6 → depends on FP-5 (determinism must pass before performance baseline)
FP-3 → can execute in parallel with FP-4 and FP-5 once OQ-1 is resolved
```

---

## SECTION 11 — OPEN QUESTIONS REQUIRING CTO DECISION

### OQ-1 (HIGH — blocks FP-3)
**Question:** What is the intended semantic and formula for the `volatility` feature consumed by `position_sizing`?  
**Options:**
- A. Map `volatility → normalized_atr` (percentage ATR, already computed)
- B. Map `volatility → rolling_std` scaled to daily (returns-based, requires sqrt scaling)
- C. Add a new dedicated `daily_vol` transformer (raw volatility targeting definition)  
**Impact:** FP-3 implementation depends on this decision.  
**Current safe state:** Default fallback `vol = 0.02` ensures position sizing remains operational.

### OQ-2 (MEDIUM — FP-6 planning)
**Question:** What is the acceptable per-tick latency budget for `compute_and_store()`?  
**Context:** PA-5 measured `process_tick()` at p50 ≈ 0.7–1.0 μs. Feature computation is orders of magnitude slower (DataFrame allocation, pandas rolling). Is there a target budget (e.g., < 1 ms per tick)?  
**Impact:** FP-6 baseline targets.

### OQ-3 (LOW — FP-5 planning)
**Question:** What is the required offline store retention policy?  
**Options:**
- A. Rolling last-N DataFrame snapshots per (name, version, symbol)
- B. Time-bounded (e.g., 24-hour window)
- C. No offline persistence for online-only (live/paper) use cases  
**Current safe state:** Offline store unused by production consumers; bounded by session duration.

---

## SECTION 12 — FP-0 GATE CLASSIFICATION

```text
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║   SPRINT-004 FP-0 CONTRACT DEFINITION GATE:                                ║
║   COMPLETE — AWAITING CTO AUTHORIZATION TO PROCEED TO FP-1                 ║
║                                                                            ║
║   Decisions Recorded: 10 (ADR-001 through ADR-010)                         ║
║   Open Questions Requiring CTO Input: 3 (OQ-1 blocks FP-3)                ║
║                                                                            ║
║   Resolved:                                                                ║
║   ✅ ATR canonical source: pa_orch.get_atr() (ADR-001)                     ║
║   ✅ StrategyLoop extract_features(): dead code; fix in FP-2 (ADR-002)     ║
║   ✅ EventBus role: audit/observability only in Sprint 004 (ADR-003)       ║
║   ✅ Feature registration: one-time at startup, not per-tick (ADR-004)     ║
║   ✅ store.query_latest(): boundary violation; fix in FP-2 (ADR-005)       ║
║   ✅ Offline store retention: undefined, deferred to FP-5 (ADR-006)        ║
║   ✅ Determinism: functionally confirmed; as_of_time exists (ADR-007)      ║
║   ✅ volatility: safe fallback exists; definition UNRESOLVED (ADR-008)     ║
║   ✅ SessionUpdated: stub, out of Sprint 004 scope (ADR-009)               ║
║   ✅ Parallel structure detection stacks: no consolidation in S004 (ADR-010)║
║                                                                            ║
║   Unresolved (require CTO decision before respective FP stage):            ║
║   🟡 OQ-1: volatility feature semantic (blocks FP-3)                       ║
║   🟡 OQ-2: acceptable per-tick latency budget for feature pipeline         ║
║   🟡 OQ-3: offline store retention policy                                  ║
║                                                                            ║
║   Production Python Files Modified: 0                                     ║
║   New Tests Created: 0                                                     ║
║                                                                            ║
║   Next authorized stage: FP-1 (Feature Registration Lifecycle)             ║
║   STOP. Awaiting CTO authorization.                                        ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
```

---

**STOP.** FP-0 is complete. Returning for CTO review. No further work until authorization.
