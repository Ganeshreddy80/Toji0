# SPRINT 004 — FP-3 VOLATILITY SEMANTICS CONTRACT GATE
## Discovery & Contract Proposal

**Author:** TOJI Senior Staff Engineer  
**Date:** 2026-08-12  
**Governance:** Master Architecture Governance — Sprint 004 / FP-3 Volatility Semantics  
**Predecessor:** `SPRINT-004-FP2-IMPLEMENTATION-GATE.md` — **CERTIFIED PASS**  
**Stage:** FP-3 — VOLATILITY SEMANTICS — DISCOVERY / CONTRACT  
**Status:** **PASS — CONTRACT READY FOR CTO APPROVAL**

> **IMPORTANT:** This is a DISCOVERY and CONTRACT document only.  
> Zero production Python files were modified during this stage.  
> Implementation has NOT started.  

---

## 1. EXECUTIVE SUMMARY

This document resolves **CTO Open Question OQ-1**: *"What exactly does the Feature Platform feature `volatility` mean?"*

The audit reveals a **critical architectural gap**: the Feature Platform canonical feature registry (`DEFAULT_FEATURE_DEFINITIONS`) contains **no registered feature named `volatility`**. The feature name `"volatility"` is used as a lookup key by two production CRITICAL-risk consumers (`PositionSizingOrchestrator` — volatility and risk_parity methods) with no registered transformer, no DAG node, and no computed output backing it. Every query for `"volatility"` from `FeaturePlatformOrchestrator.query_realtime()` returns an empty or null result today.

Three semantically distinct volatility-related concepts exist in the codebase:
- **`normalized_atr`** — ATR/close (dimensionless ratio). Registered, computed, stored. Transformer: `NormalizedAtrTransformer`.
- **`rolling_std`** — rolling std of log returns, window 20. Registered, computed, stored. Transformer: `RollingStdTransformer`.
- **`atr`** — raw Average True Range (price units). Registered, computed, stored. Transformer: `AtrTransformer`.
- **PA-ATR** — `PriceActionOrchestrator.get_atr(symbol)` — per-bar SMA(TR, 14) in price units. Separate stack. ADR-001 authoritative source.
- **`VolatilityFeature`** — legacy `data/feature_store/definitions.py`. Rolling std of pct_change of close, window 20. **Disconnected from Feature Platform. Not registered.**

None of these are named `"volatility"` in the Feature Platform. The `"volatility"` key requested by `PositionSizingOrchestrator` is a **phantom feature** — it resolves to nothing at runtime.

---

## 2. CTO OPEN QUESTION OQ-1

> *"What exactly does the Feature Platform feature `volatility` mean?"*

**Short Answer from Evidence:** The Feature Platform has NO registered, computed, or stored feature named `"volatility"`. The name `"volatility"` is requested as a query key by production consumers, but no Feature Platform transformer produces it. All downstream consumers requesting `"volatility"` silently fall back to the hardcoded default `vol = 0.02`.

---

## 3. REPOSITORY EVIDENCE

### 3.1 Files Inspected

| File | Purpose |
|---|---|
| `research_platform/feature_platform/orchestrator.py` | Canonical feature registry (`DEFAULT_FEATURE_DEFINITIONS`), `query_realtime()` |
| `research_platform/feature_platform/feature_pipeline.py` | DAG transformer registry |
| `research_platform/feature_platform/transformers.py` | All transformer implementations |
| `research_platform/position_sizing/orchestrator.py` | Primary `"volatility"` consumer |
| `research_platform/position_sizing/models.py` | `SizingConfig` (target_volatility = 0.10) |
| `research_platform/exit_engine/orchestrator.py` | `normalized_atr`, `risk_score` consumer |
| `research_platform/exit_engine/models.py` | `ExitEngineConfig` volatility_threshold |
| `research_platform/ai_signal/signal_generator.py` | PA-ATR consumer |
| `research_platform/trade_journal/orchestrator.py` | Feature query for memory logging |
| `research_platform/runtime/strategy_loop.py` | Feature query orchestration |
| `research_platform/price_action/orchestrator.py` | PA-ATR implementation (`_calculate_atr`) |
| `research_platform/portfolio_intelligence/risk_parity.py` | `RiskParityAllocator.calculate_weights()` |
| `research_platform/strategy_lab/position_sizing.py` | `PositionSizer.VolatilityTarget` formula |
| `research_platform/validation_core/regime.py` | `MarketRegimeClassifier` uses `np.std(sub)` threshold `0.02` |
| `data/feature_store/definitions.py` | Legacy `VolatilityFeature` (disconnected) |

### 3.2 The Canonical Feature Registry — `DEFAULT_FEATURE_DEFINITIONS`

The Feature Platform registers exactly these 20 features at startup:

| Level | Feature Name | Formula / Transformer |
|---|---|---|
| 0 (Raw) | `open`, `high`, `low`, `close`, `volume` | PassThrough |
| 1 (Derived) | `log_return` | `log(close/close_prev)` |
| 1 (Derived) | `atr` | `SMA(TrueRange, 14)` |
| 1 (Derived) | `ema9`, `ema21`, `ema50` | `EMA(close, N)` |
| 1 (Derived) | `rsi` | `RSI(close, 14)` |
| 1 (Derived) | `volume_change` | `pct_change(volume)` |
| 1 (Derived) | `support` | `rolling_min(low, 20)` |
| 1 (Derived) | `resistance` | `rolling_max(high, 20)` |
| 2 (Derived) | `rolling_std` | `std(log_return, 20)` |
| 2 (Derived) | `normalized_atr` | `atr / close` |
| 2 (Derived) | `breakout` | `breakout(close, resistance, support)` |
| 2 (Derived) | `trend` | `trend(ema9, ema21)` |
| 3 (Derived) | `risk_score` | `zscore(normalized_atr, 50)` |
| 4 (Derived) | `signal` | `signal(risk_score, 2.0)` |

**`"volatility"` does NOT appear in this list.**

---

## 4. CONSUMER MATRIX

### Consumer 1: PositionSizingOrchestrator — `method="volatility"`

| Attribute | Evidence |
|---|---|
| **File** | `research_platform/position_sizing/orchestrator.py` |
| **Class/Function** | `PositionSizingOrchestrator.calculate_size()` L114–127 |
| **Feature Requested** | `"volatility"` (string literal) |
| **Why Requested** | Position sizing: `target_capital = equity * (target_volatility / max(vol, 0.001))` |
| **Mathematical Meaning Expected** | Asset's current realized volatility (a dimensionless fraction) to be compared against `target_volatility` (config default 0.10 = 10%) |
| **Units Expected** | Dimensionless fraction (e.g. 0.02 = 2%) |
| **Timeframe** | NOT DEFINED IN CURRENT SOURCE |
| **Lookback** | NOT DEFINED IN CURRENT SOURCE |
| **Fallback Behavior** | `vol = 0.02` when feature unavailable |
| **What Happens if Missing** | Silent fallback to `vol = 0.02`; position size calculated as if asset volatility is exactly 2% |
| **Affects Money/Risk/Orders?** | **YES — CRITICAL**. Determines raw quantity for `method="volatility"` sizing. Directly drives `raw_qty`. |
| **Current Implementation Satisfies?** | **NO.** `"volatility"` does not exist in Feature Platform. Every call returns empty DataFrame. Always falls back to 0.02. |

### Consumer 2: PositionSizingOrchestrator — `method="risk_parity"`

| Attribute | Evidence |
|---|---|
| **File** | `research_platform/position_sizing/orchestrator.py` |
| **Class/Function** | `PositionSizingOrchestrator.calculate_size()` L136–152 |
| **Feature Requested** | `"volatility"` (string literal) |
| **Why Requested** | Risk parity weighting: `Weight_i = (1/Vol_i) / Sum(1/Vol_j)` |
| **Mathematical Meaning Expected** | Realized per-asset volatility (fraction) for inverse-volatility weighting against a baseline `{symbol: vol, "baseline": 0.02}` |
| **Units Expected** | Dimensionless fraction |
| **Timeframe** | NOT DEFINED IN CURRENT SOURCE |
| **Lookback** | NOT DEFINED IN CURRENT SOURCE |
| **Fallback Behavior** | `vol = 0.02` when feature unavailable |
| **What Happens if Missing** | Parity weight computed as `weights[symbol]` against baseline both at 0.02 → equal weight (0.5) |
| **Affects Money/Risk/Orders?** | **YES — CRITICAL**. Determines capital allocation weight and raw quantity. |
| **Current Implementation Satisfies?** | **NO.** `"volatility"` does not exist. Always falls back to 0.02 and yields equal weighting. |

### Consumer 3: ExitEngineOrchestrator — `normalized_atr` / `risk_score`

| Attribute | Evidence |
|---|---|
| **File** | `research_platform/exit_engine/orchestrator.py` |
| **Class/Function** | `ExitEngineOrchestrator.on_valuation_update()` L126–238 |
| **Feature Requested** | `"atr"`, `"normalized_atr"`, `"risk_score"` |
| **Why Requested** | ATR-based stop calculation: `dist = atr_multiplier * atr`. Volatility threshold exit: `norm_atr > volatility_threshold`. Risk score exit: `risk_score > risk_score_threshold`. |
| **Mathematical Meaning Expected** | `atr` = absolute price distance. `normalized_atr` = ATR/close (dimensionless). `risk_score` = z-score of normalized_atr over 50 bars. |
| **Units Expected** | `atr`: price units. `normalized_atr`: dimensionless [0, ~0.05 typical]. `risk_score`: standard deviations (unbounded). |
| **Fallback Behavior** | All three nullable. Exit rules simply skip if None. |
| **Affects Money/Risk/Orders?** | **YES — HIGH**. Controls stop-loss distance and emergency exit triggers. |
| **Current Implementation Satisfies?** | **PARTIALLY.** `atr`, `normalized_atr`, `risk_score` ARE registered. However, feature values are only populated after `compute_and_store()` is called with sufficient bar history (warm-up ≥ 14 bars for ATR, ≥ 50 bars for risk_score). During warm-up, all are None/empty. |

### Consumer 4: AISignalGenerator — PA-ATR (not Feature Platform)

| Attribute | Evidence |
|---|---|
| **File** | `research_platform/ai_signal/signal_generator.py` |
| **Class/Function** | `AISignalGenerator.generate_signal()` L26 |
| **Feature Requested** | `pa_orch.get_atr(symbol)` — Price Action ATR, NOT Feature Platform |
| **Why Requested** | Stop-loss / take-profit distance: `sl = price - 1.5 * atr`, `tp = price + 3.0 * atr` |
| **Mathematical Meaning Expected** | Average True Range in price units |
| **Timeframe** | 1-minute bars |
| **Lookback** | 14 bars (simple moving average of TR) |
| **Fallback Behavior** | `atr = current_price * 0.01` when ATR is 0 (1% of price) |
| **Affects Money/Risk/Orders?** | **YES — CRITICAL**. Directly determines SL/TP distances which drive risk-reward and signal viability. |
| **Current Implementation Satisfies?** | **YES** (per ADR-001). PA-ATR is the authorized canonical source for ATR used in signal generation. |

### Consumer 5: TradeJournalOrchestrator

| Attribute | Evidence |
|---|---|
| **File** | `research_platform/trade_journal/orchestrator.py` L191–208 |
| **Feature Requested** | `"rsi"`, `"ema9"`, `"ema21"`, `"ema50"`, `"atr"`, `"trend"`, `"support"`, `"resistance"`, `"breakout"`, `"volume_change"` |
| **Why Requested** | Records feature snapshot at trade time for memory engine |
| **Volatility Requested?** | **No.** No `"volatility"` requested. |
| **Affects Money/Risk/Orders?** | **LOW** — informational/logging only |

### Consumer 6: StrategyLoop

| Attribute | Evidence |
|---|---|
| **File** | `research_platform/runtime/strategy_loop.py` L28–36 |
| **Feature Requested** | All registered features (dynamic) — does not specifically request `"volatility"` |
| **Affects Money/Risk/Orders?** | **MEDIUM** — routes feature context to signal generation |

### Consumer 7: StrategyLab PositionSizer

| Attribute | Evidence |
|---|---|
| **File** | `research_platform/strategy_lab/position_sizing.py` L19, 47–50 |
| **Feature Requested** | Not Feature Platform — receives `volatility: float = 0.02` as parameter |
| **Mathematical Meaning Expected** | "current asset rolling volatility percentage" per docstring L28 |
| **Affects Money/Risk/Orders?** | **HIGH** (backtesting context). Drives VolatilityTarget position size in strategy lab. |

---

## 5. MATHEMATICAL DEFINITIONS

### 5A. `normalized_atr` (REGISTERED — Feature Platform)

```
Formula:       normalized_atr = ATR(14) / (close + 1e-10)
Input Series:  high, low, close (1-minute OHLCV)
Transformer:   NormalizedAtrTransformer
Timeframe:     1-minute bars
Lookback:      14 bars (inherited from atr dependency)
Units:         Dimensionless ratio [typical range 0.001–0.05 for crypto]
Output Range:  [0, ~0.10] for normal markets
Warm-up:       15 bars minimum (1 for prev_close shift + 14 for ATR window)
Zero-price:    Protected via (close + 1e-10) — will not divide by zero
NaN behavior:  fillna(0.0) applied after division
Missing data:  Returns 0.0 for missing inputs
Is Annualized: NO
Is Dimensionless: YES
Suitable for Position Sizing: PARTIALLY — dimensionless ratio is appropriate for
                               volatility target sizing. However it is ATR-based
                               (range-based), not returns-based (statistical vol).
                               Does not require annualization scaling for
                               percentage-based position sizing formulas.
```

### 5B. `rolling_std` (REGISTERED — Feature Platform)

```
Formula:       rolling_std = std(log(close/close_prev), window=20)
Input Series:  close (via log_return dependency)
Transformer:   RollingStdTransformer(target="log_return", window=20)
Timeframe:     1-minute bars
Lookback:      21 bars (1 for log_return shift + 20 for rolling window)
Units:         Dimensionless — std of log returns (per-bar, 1-minute basis)
Output Range:  [0, ~0.02] typical per 1-minute bar for crypto
Warm-up:       21 bars minimum
Zero-price:    Inherited from LogReturnTransformer (handles via log)
NaN behavior:  fillna(0.0) applied
Missing data:  Returns 0.0
Is Annualized: NO — per-bar 1-minute volatility (to annualize: multiply by sqrt(525600))
Is Dimensionless: YES
Suitable for Position Sizing: YES — but requires annualization or consistent
                               interpretation if compared to a target_volatility
                               that is expressed on a different timeframe.
                               Current config target_volatility=0.10 (10%) is
                               likely annualized, creating a scale mismatch.
```

### 5C. `atr` (REGISTERED — Feature Platform)

```
Formula:       atr = SMA(TrueRange, 14), where
               TrueRange = max(high-low, |high-prev_close|, |low-prev_close|)
Transformer:   AtrTransformer(window=14)
Timeframe:     1-minute bars
Lookback:      15 bars (1 shift + 14 rolling)
Units:         Price units (USD, BTC, etc.) — NOT dimensionless
Output Range:  [0, ∞) — dependent on asset price level
Warm-up:       15 bars minimum
Zero-price:    Handled — first bar fills prev_close with close
NaN behavior:  fillna(0.0)
Is Annualized: NO
Is Dimensionless: NO
Suitable for Position Sizing: NOT directly — requires normalization by price
                               to become dimensionless for volatility sizing formulas.
```

### 5D. PA-ATR — `PriceActionOrchestrator.get_atr(symbol)` (ADR-001 canonical)

```
Formula:       PA_ATR = mean(TrueRange[-14:]), where
               TrueRange = max(high-low, |high-prev_close|, |low-prev_close|)
               computed on 1-minute OHLCV bars aggregated from ticks
Algorithm:     Simple arithmetic mean of last 14 True Ranges (NOT exponential like Wilder)
Timeframe:     1-minute bars
Lookback:      14 bars (or fewer during warm-up — no guard against < 14 bars)
Units:         Price units
Output Range:  [0, ∞) — price-denominated
Warm-up:       Computed from bar 2 onwards (tr_list has 1+ entries)
               NOTE: During early bars (<14), SMA is over fewer than 14 periods.
               This is a soft warm-up: ATR rises toward stable estimate.
Zero-price:    Handled implicitly — no explicit guard, but TR must be ≥ 0
NaN behavior:  Returns 0.0 (dict.get default)
Is Annualized: NO
Is Dimensionless: NO
Suitable for Position Sizing: NOT directly — used for stop distances in price terms.
Relationship to Feature Platform `atr`: SAME formula conceptually (SMA of TR, 14 bars).
                                        Computed from SAME 1-minute bars.
                                        Different computation stacks (separate in-memory state).
                                        Will diverge if tick streams differ between stacks.
```

### 5E. Legacy `VolatilityFeature` — `data/feature_store/definitions.py`

```
Formula:       volatility = pct_change(close).rolling(period=20).std()
               = std of simple percentage returns over 20 bars
Input Series:  close
Timeframe:     1-minute bars (assumed, context-dependent)
Lookback:      21 bars (1 for pct_change shift + 20 for rolling)
Units:         Dimensionless — std of percentage returns
Output Range:  [0, ~0.02] per 1-minute bar for normal crypto markets
Warm-up:       21 bars minimum
NaN behavior:  Returns NaN (no fillna applied — intentional: avoids masking warm-up)
Is Annualized: NO
Is Dimensionless: YES
Suitable for Position Sizing: YES — semantically cleanest definition for
                               "current asset volatility as a dimensionless fraction"
                               for use in volatility-target position sizing.
Connection to Feature Platform: NONE. This class is in data/feature_store/definitions.py,
                                NOT registered in FeaturePlatformOrchestrator.
                                NOT accessible via query_realtime().
```

### 5F. `risk_score` (REGISTERED — Feature Platform)

```
Formula:       risk_score = zscore(normalized_atr, window=50)
               = (normalized_atr - rolling_mean(normalized_atr, 50)) /
                 (rolling_std(normalized_atr, 50) + 1e-10)
Input Series:  normalized_atr (which depends on atr, close)
Transformer:   RiskScoreTransformer(vol_column="normalized_atr", window=50)
Timeframe:     1-minute bars
Lookback:      50 bars + 14 bars ATR dependency = effective 65 bars warm-up
Units:         Standard deviations (unbounded — typically [-3, +3])
Output Range:  Centered around 0 with std ≈ 1.0 in steady state
Warm-up:       65 bars minimum
Is Annualized: NO
Is Dimensionless: YES (standard deviations)
Suitable for Position Sizing: NO — this is a relative risk indicator,
                               not an absolute volatility measure.
                               Higher risk_score means normalized_atr is
                               currently elevated vs. recent history.
```

---

## 6. SEMANTIC COMPARISON

| Concept | Type | Units | Registered | Directly suitable for position sizing |
|---|---|---|---|---|
| `normalized_atr` | ATR / close | Dimensionless ratio | ✅ YES | Partially (range-based, not returns-based) |
| `rolling_std` | std(log_returns, 20) | Per-bar (1m) | ✅ YES | Yes, with consistent timeframe interpretation |
| `atr` | SMA(TR, 14) | Price units | ✅ YES | No — not dimensionless |
| `risk_score` | zscore(normalized_atr, 50) | Std deviations | ✅ YES | No — relative indicator |
| `"volatility"` (requested by consumers) | **PHANTOM** — does not exist | N/A | ❌ NO | N/A |
| `VolatilityFeature` (legacy) | std(pct_change, 20) | Per-bar | ❌ NO (disconnected) | Yes |
| PA-ATR | SMA(TR, 14) | Price units | External | No — not dimensionless |

### Semantic Mismatch Findings

1. **`normalized_atr` vs `rolling_std`:** Semantically different. `normalized_atr` is a range-based measure (intrabar price spread relative to price). `rolling_std` is a returns-based measure (statistical variation in log returns). They are correlated but not equivalent. In trending markets they may diverge significantly.

2. **`risk_score` is NOT volatility:** It is the z-score of `normalized_atr` over 50 bars. It measures whether current ATR is high or low relative to recent history. This is a regime indicator, not an absolute volatility level. It is NOT suitable as input to `target_capital = equity * (target_volatility / vol)`.

3. **`atr` vs `normalized_atr`:** Related by `normalized_atr = atr / close`. Not equivalent. ATR is in price units; normalized_atr is dimensionless.

4. **PA-ATR vs Feature Platform `atr`:** Same algorithm (SMA of TR over 14 bars) on the same 1-minute bars. Two separate in-memory computation stacks. Values are expected to be equivalent at steady state if the same tick stream feeds both, but there is no guarantee of exact numerical identity.

---

## 7. FALLBACK ANALYSIS — `0.02`

### Where `0.02` Appears in Volatility Context

| Location | Context | Interpretation |
|---|---|---|
| `position_sizing/orchestrator.py` L117 | `vol = 0.02` | Default asset volatility when `"volatility"` query returns empty |
| `position_sizing/orchestrator.py` L138 | `vol = 0.02` | Default asset volatility for risk parity |
| `position_sizing/orchestrator.py` L146 | `"baseline": 0.02` | Hardcoded baseline asset volatility for risk parity comparison |
| `strategy_lab/position_sizing.py` L19 | `volatility: float = 0.02` | Function parameter default |
| `validation_core/regime.py` L37 | `if vol > 0.02` | Regime classifier threshold for "volatile" classification |
| `risk_management/position_risk.py` L13 | `max_risk_per_trade: float = 0.02` | Risk per trade (2%) — NOT a volatility default |

### Fallback Analysis

| Question | Finding |
|---|---|
| Where does 0.02 originate? | Hardcoded inline in `PositionSizingOrchestrator.calculate_size()`. No named constant. No configuration parameter. No documentation. |
| Which consumers use it? | Both `method="volatility"` and `method="risk_parity"` paths in `PositionSizingOrchestrator` |
| Why does it exist? | As a guard against division by zero and to ensure position sizing produces a non-zero result when feature data is unavailable |
| Does it represent 2%? | **Likely intended as 2% per-bar or 2% daily volatility**, consistent with typical crypto volatility, but this is **NOT DOCUMENTED IN CURRENT SOURCE** |
| Is the 2% interpretation documented? | **NOT DEFINED IN CURRENT SOURCE.** No docstring, comment, or configuration key explains this value's units, timeframe, or derivation. |
| Is it safe for position sizing? | **UNKNOWN.** The safety depends entirely on which volatility definition is eventually resolved. If the canonical `volatility` is annualized, `0.02` (2%) is unrealistically low. If per-bar 1-minute, `0.02` may be high. The value is not validated against market data. |
| Does it mask missing computation? | **YES.** Because `"volatility"` is not registered, every call silently falls back to `0.02`. The position sizing subsystem operates on a phantom constant, not live feature data. |
| Is it appropriate during warm-up? | **UNKNOWN.** The warm-up regime is not considered. There is no distinction between "warm-up not yet complete" and "feature does not exist". Both are silently collapsed to `0.02`. |

---

## 8. RISK IMPACT CLASSIFICATION

| Consumer | Impact Classification | Rationale |
|---|---|---|
| `PositionSizingOrchestrator` — `method="volatility"` | **CRITICAL** | Directly determines raw trade quantity via `target_capital / price`. Affects capital allocation and exposure. |
| `PositionSizingOrchestrator` — `method="risk_parity"` | **CRITICAL** | Determines weight in portfolio via inverse-vol weighting. Affects capital allocation across all positions. |
| `ExitEngineOrchestrator` — `normalized_atr` / `risk_score` | **HIGH** | Controls stop distances (`atr_multiplier * atr`) and emergency exit thresholds. Affects realized stop-loss levels and maximum losses. |
| `ExitEngineOrchestrator` — `volatility_threshold` | **HIGH** | Compares `normalized_atr` against a configured threshold for emergency exits. |
| `AISignalGenerator` — PA-ATR | **CRITICAL** | Directly computes SL/TP distances. Drives signal execution viability. |
| `TradeJournalOrchestrator` | **LOW** | Memory/logging only. No order impact. |
| `StrategyLoop` | **MEDIUM** | Routes feature context to signals. Does not directly drive sizing. |
| `StrategyLab PositionSizer` | **HIGH** | Backtesting context. Drives VolatilityTarget sizing in strategy experiments. |
| `ValidationCore / MarketRegimeClassifier` | **MEDIUM** | Regime classification threshold. Affects research/analytics outputs. |

---

## 9. CANONICAL SOURCE ANALYSIS

### Option A: PriceAction ATR → Normalized Volatility

Use `PriceActionOrchestrator.get_atr(symbol) / current_price` as the canonical `"volatility"`.

| Dimension | Assessment |
|---|---|
| **Advantages** | PA-ATR is ADR-001 authoritative. Already computed per-tick. No additional registration needed. Used for SL/TP by AISignalGenerator (existing consumers aligned). |
| **Disadvantages** | PA-ATR is in price units — requires normalization by current price (not always available in Feature Platform context). Creates cross-subsystem dependency: Feature Platform consumers would need to access PriceActionOrchestrator. Violates Feature Platform self-containment. |
| **Duplication Risk** | Creates dual ATR computation paths (PA and FP). Both run SMA(TR,14) on the same 1-minute bars. |
| **Determinism** | Uncertain — two independent stacks on same data source. Race conditions if tick order differs. |
| **Dependency** | Requires FP consumers to resolve PriceActionOrchestrator. Breaks clean dependency boundary. |
| **Downstream Compatibility** | Disrupts current consumers. AISignalGenerator already accesses PA-ATR directly. PositionSizing has no PA access today. |
| **Migration Cost** | HIGH — requires injection of PA orchestrator into position sizing and other FP consumers. |
| **ADR-001 Fit** | Partially consistent — ADR-001 names PA ATR as canonical for "downstream ATR". But that was defined for Feature Platform's internal ATR feature (DAG-only). |
| **Risk** | Creates a tight coupling between PA and FP that was explicitly rejected by ADR-010 (parallel stacks unchanged). |

**Assessment: NOT RECOMMENDED.**

---

### Option B: Feature Platform `normalized_atr` → `volatility`

Register `normalized_atr` as the canonical definition of `"volatility"` or create a `"volatility"` feature as an alias.

| Dimension | Assessment |
|---|---|
| **Advantages** | `normalized_atr` is already registered, computed, and stored. It is dimensionless (ATR/close). Directly usable in sizing formula without unit conversion. ExitEngine already uses it for volatility-threshold exits. Architecturally clean. |
| **Disadvantages** | ATR-based (range-based) volatility, not returns-based (statistical). Does not represent "rolling standard deviation of returns" which is the conventional academic/practitioner definition. Lookback is 14 bars vs. common 20 for statistical vol. |
| **Duplication Risk** | LOW — single registered feature, no new transformer needed. |
| **Determinism** | HIGH — single computation path within Feature Platform DAG. |
| **Dependency** | NONE — already in DAG. Position sizing just needs to query `"normalized_atr"` instead of `"volatility"`. |
| **Downstream Compatibility** | Minimal migration — change query key from `"volatility"` to `"normalized_atr"` in `PositionSizingOrchestrator`. |
| **Migration Cost** | LOW — query key rename in 2 locations in `position_sizing/orchestrator.py`. |
| **ADR-001 Fit** | Consistent. `normalized_atr` is an FP-internal DAG feature. Not in conflict with PA ATR (ADR-001 governs PA as source for downstream ATR features; normalized_atr is already computed from FP-internal `atr`). |
| **Risk** | Semantically imprecise for statisticians. Range-based vol is not identical to returns-based vol. However for position sizing purposes, both serve the same function — quantifying risk per unit price. |

**Assessment: RECOMMENDED (primary option).**

---

### Option C: Feature Platform `rolling_std` → `volatility`

Register `rolling_std` (std of log returns, window 20) as `"volatility"`.

| Dimension | Assessment |
|---|---|
| **Advantages** | Academically standard definition of realized volatility (Garman-Klass, close-to-close). Returns-based. Dimensionless. Window 20 matches industry convention for monthly realized vol. |
| **Disadvantages** | Already registered as `rolling_std`. Renaming or aliasing creates conceptual confusion. The value is per-1-minute-bar and is numerically very small (~0.001–0.005 per bar). Position sizing formula `target_capital = equity * (target_volatility / vol)` with `target_volatility=0.10` and `vol=0.002` would produce enormous leverage (50x). Without explicit timeframe normalization, this is dangerous. |
| **Duplication Risk** | LOW — already registered. |
| **Determinism** | HIGH — single DAG path. |
| **Scale Mismatch Risk** | **CRITICAL** — `rolling_std` is per-1-minute-bar. `target_volatility=0.10` (10%) is almost certainly intended as annualized or daily. Without normalization, the sizing formula will produce extreme quantities. |
| **Migration Cost** | LOW to MEDIUM — query key change + documentation. But requires verifying scale/timeframe interpretation with CTO. |
| **ADR-001 Fit** | Consistent (FP internal feature). |
| **Risk** | Scale mismatch between per-bar `rolling_std` and annualized `target_volatility` creates risk of extreme position sizes. **NOT SAFE** without explicit normalization factor. |

**Assessment: NOT RECOMMENDED without explicit annualization contract.**

---

### Option D: Dedicated Volatility Transformer

Create a new `"volatility"` feature with its own transformer (e.g., `VolatilityTransformer` = std of pct_change, window 20, similar to legacy `VolatilityFeature`).

| Dimension | Assessment |
|---|---|
| **Advantages** | Allows bespoke definition tuned for position sizing. Can document exact units and timeframe explicitly in the transformer. Clean separation. |
| **Disadvantages** | Requires new production code (violates discovery-only phase). Duplicates `rolling_std` (conceptually very similar). Adds DAG complexity. Requires registration, dependency declaration, and warm-up management. |
| **Duplication Risk** | HIGH — effectively duplicates `rolling_std` or `normalized_atr` with a different name. |
| **Migration Cost** | HIGH — new transformer, registration, tests, validation. |
| **ADR-001 Fit** | Consistent (FP internal). |
| **Risk** | Scope creep. Complexity. Deferred to FP-3 implementation phase. |

**Assessment: POSSIBLE for FP-3 implementation, but only if Option B is rejected. Adds significant scope.**

---

## 10. RECOMMENDED CONTRACT

### Recommendation: Option B — `normalized_atr` as Canonical Volatility Definition

**Based strictly on repository evidence and architectural constraints.**

| Attribute | Contract Value |
|---|---|
| **Feature name** | `"volatility"` — resolves to `normalized_atr` semantics |
| **Mathematical definition** | `normalized_atr = SMA(TrueRange, 14) / (close + 1e-10)` |
| **Unit** | Dimensionless ratio (fraction of price) |
| **Timeframe** | 1-minute bars |
| **Lookback** | 15 bars minimum (14 ATR + 1 prev_close shift) |
| **Canonical source** | `FeaturePlatformOrchestrator.query_realtime(["normalized_atr"], [symbol])` |
| **How consumed** | `PositionSizingOrchestrator` requests `"normalized_atr"` directly (not `"volatility"`) |
| **Fallback behavior** | `vol = 0.02` when `normalized_atr` is unavailable (warm-up or missing data) |
| **Warm-up behavior** | During warm-up (< 15 bars for ATR), `normalized_atr` = 0.0 (fillna). Fallback `vol = 0.02` provides continuity. |
| **NaN behavior** | `NormalizedAtrTransformer` applies `fillna(0.0)`. No NaN propagates to consumers. |
| **Zero/invalid input behavior** | `(close + 1e-10)` guard prevents division by zero. Zero ATR (insufficient bars) returns 0.0 → fallback to 0.02. |
| **Consumers** | `PositionSizingOrchestrator` (`method="volatility"`, `method="risk_parity"`) |
| **Validation requirements** | `normalized_atr` must be in range `[0, 0.15]` for normal crypto. Values > 0.15 indicate extreme volatility events — should not silently override position sizing. |

**Note:** This contract does NOT require creating a new `"volatility"` feature name in the registry. Instead, the production change is: `PositionSizingOrchestrator` should query `"normalized_atr"` directly rather than the phantom key `"volatility"`. No new transformer. No new registration. No new DAG node.

---

### Separation: Repository Evidence vs. Engineering Recommendation

**Repository Evidence (observed facts):**
1. The feature name `"volatility"` is not registered in `DEFAULT_FEATURE_DEFINITIONS`.
2. `PositionSizingOrchestrator` queries `"volatility"` via `query_realtime()` and receives an empty DataFrame every time.
3. Both volatility sizing methods silently fall back to `vol = 0.02`.
4. `normalized_atr` IS registered, IS computed, IS stored, and IS semantically appropriate for dimensionless position sizing.
5. `rolling_std` IS registered but produces per-bar values that will create scale mismatch with the `target_volatility=0.10` config if used directly.
6. PA-ATR is the only other ATR source — it is in price units and lives in a separate subsystem.
7. `ExitEngineOrchestrator` already successfully uses `normalized_atr` for its volatility threshold exit rule.

**Engineering Recommendation (judgment calls):**
1. Map `"volatility"` → `"normalized_atr"` semantics. This is a rename/redirect at the consumer query layer — not a new feature.
2. The `0.02` fallback value represents a conservative default normalized_atr (2% ATR relative to price, i.e., typical crypto). This interpretation is consistent with the `normalized_atr` definition. The fallback should remain.
3. `target_volatility = 0.10` in `SizingConfig` should be re-evaluated: if the resolved `vol` is `normalized_atr` (typical range 0.005–0.020 for 1m crypto), then `target_volatility / vol` produces leverage of 5–20x, which may be correct for a volatility targeting strategy but must be explicitly confirmed by CTO.

---

## 11. OPEN QUESTIONS

| # | Question | Blocking? |
|---|---|---|
| OQ-1a | Is the position sizing formula `target_capital = equity * (target_volatility / vol)` intended for dimensionless `vol` in the range [0.005, 0.02]? Or is `target_volatility` meant to match a different timeframe? | **YES** — affects whether Option B or C is correct. |
| OQ-1b | Is `target_volatility = 0.10` (10%) intended as annualized, daily, or per-minute volatility? | **YES** — determines scale compatibility with `normalized_atr`. |
| OQ-2 | Should `"volatility"` remain as a distinct named feature key in the Feature Platform registry, or should consumers simply query `"normalized_atr"` directly? | YES — affects implementation scope. |
| OQ-3 | Is the `0.02` fallback intended to represent `normalized_atr ≈ 2%` (ATR is 2% of price) or `rolling_std ≈ 2%` per-bar standard deviation of returns? | YES — determines if fallback value is appropriate for either definition. |
| OQ-4 | Is `ExitEngineOrchestrator.config.volatility_threshold` interpreted in the same units as `normalized_atr`? (Range [0.0, ~0.05] typical.) Is this documented? | MEDIUM — affects exit engine threshold configuration. |

---

## 12. EXPLICIT SCOPE EXCLUSIONS

No production code was modified during FP-3 discovery.

The following are explicitly EXCLUDED from this stage:

| Item | Status |
|---|---|
| Modifying `PositionSizingOrchestrator` query key | DEFERRED — FP-3 Implementation |
| Adding `"volatility"` feature to registry | DEFERRED — pending CTO option selection |
| Creating new `VolatilityTransformer` | DEFERRED (Option D — only if CTO rejects Option B) |
| Modifying `target_volatility` configuration | NOT IN SCOPE — CTO decision required |
| Modifying ExitEngine volatility threshold | NOT IN SCOPE |
| FP-4 (ATR Migration) | NOT IN SCOPE |
| FP-5 (FeatureStore Retention) | NOT IN SCOPE |

---

## 13. PRODUCTION FILES MODIFIED

```
Production Files Modified: 0
Test Files Modified: 0
```

---

## 14. FINAL FP-3 DISCOVERY CLASSIFICATION

```text
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║   SPRINT-004 FP-3 VOLATILITY SEMANTICS — DISCOVERY GATE:                   ║
║                                                                            ║
║   PASS — CONTRACT READY FOR CTO APPROVAL                                   ║
║                                                                            ║
║   KEY FINDINGS:                                                            ║
║   • "volatility" feature: NOT REGISTERED in Feature Platform               ║
║   • Every query for "volatility" returns empty → silent 0.02 fallback      ║
║   • Fallback 0.02 meaning: NOT DOCUMENTED IN SOURCE                        ║
║   • 3 registered volatility-adjacent features: normalized_atr,             ║
║     rolling_std, risk_score                                                ║
║   • normalized_atr: dimensionless, registered, computed — RECOMMENDED      ║
║   • rolling_std: registered, but scale mismatch risk with target_vol=0.10  ║
║   • risk_score: z-score indicator — NOT suitable for position sizing        ║
║   • PA-ATR: separate stack, price-denominated — NOT suitable for FP use    ║
║                                                                            ║
║   RECOMMENDED CANONICAL DEFINITION:                                        ║
║   volatility → normalized_atr = SMA(TrueRange,14) / close                 ║
║   Unit: dimensionless fraction | Timeframe: 1m | Lookback: 15 bars         ║
║   Implementation: query "normalized_atr" directly from query_realtime()    ║
║                                                                            ║
║   CRITICAL OPEN QUESTIONS: OQ-1a, OQ-1b (scale mismatch — CTO decision)   ║
║                                                                            ║
║   Production Files Modified: 0                                             ║
║   FP-3 Implementation: NOT STARTED                                         ║
║   STOP. Awaiting CTO contract approval.                                    ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
```

---

**STOP.** FP-3 discovery and contract proposal are complete. Awaiting CTO contract approval before proceeding to FP-3 implementation.
