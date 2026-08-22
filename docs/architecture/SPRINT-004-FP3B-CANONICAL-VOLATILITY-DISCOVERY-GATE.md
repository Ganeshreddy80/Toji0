# SPRINT 004 — FP-3B
## Canonical Volatility Contract Discovery Gate

**Author:** TOJI Senior Staff Engineer / Principal Architect  
**Date:** 2026-08-13  
**Governance:** Master Architecture Governance — Sprint 004  
**Predecessor Gate:** `SPRINT-004-FP3-OQ-RESOLUTION.md` — HOLD  
**Stage:** FP-3B — DISCOVERY ONLY  
**Production Files Modified:** **0**  
**Test Files Modified:** **0**  
**Configuration Modified:** **0**

---

## 1. EXECUTIVE SUMMARY

This gate performs a complete repository-wide audit of all volatility implementations, the position-sizing formula chain, and every downstream consumer. It does not implement any changes.

**Key Findings:**

1. **`"volatility"` is NOT a registered Feature Platform feature.** The `DEFAULT_FEATURE_DEFINITIONS` list in `feature_platform/orchestrator.py` contains no entry named `"volatility"`. All production queries for `"volatility"` via `query_realtime()` return an empty DataFrame.

2. **The position-sizing formula is a dimensionless ratio.** `leverage = target_volatility / vol`. No timeframe conversion exists in the formula. The formula is agnostic to timeframe; its output depends entirely on the scale of both inputs being identical.

3. **The only explicit timeframe comment in the codebase calls the fallback "2% daily".** Source: `research_platform/position_sizing/orchestrator.py` L116. No other timeframe documentation exists for `target_volatility`.

4. **No `TARGET_VOLATILITY` or `POSITION_SIZING_METHOD` entry exists in `.env` or `.env.example`.** The environment template does not document these variables. They are code-only defaults.

5. **`normalized_atr` and `rolling_std` are both registered Feature Platform features with working transformers.** Neither is named `"volatility"`. `normalized_atr = ATR/close`. `rolling_std = std(log_return, 20)`.

6. **`ExitEngineOrchestrator` is the only current production consumer of `normalized_atr` for volatility purposes.** It uses `normalized_atr` as an exit threshold comparison. Its model explicitly labels this: `"Volatility exit threshold on normalized ATR"`.

7. **The `analytics/position_sizing/sizing.py` module (a parallel, disconnected implementation) explicitly documents its `asset_volatility` parameter as "annualized standard deviation fraction (e.g. 0.3 for 30%)" — a fundamentally different scale from the 0.005–0.025 range of `normalized_atr`.** This parallel module is not connected to the live `PositionSizingOrchestrator`.

8. **The backtesting analytics subsystem uses `annualization_factor = 252` and computes `volatility = sample_std × sqrt(252.0)`.** These are daily returns, annualized. This convention is NOT shared with or used by `PositionSizingOrchestrator`.

9. **Three parallel `target_volatility` semantics coexist in the repository:**
   - `PositionSizingOrchestrator`: `target_volatility=0.10`, fallback `vol=0.02` ("2% daily")
   - `PortfolioRebalancer`: `target_volatility=0.12`, `portfolio_volatility` at annualized scale (0.18–0.30)
   - `VolatilityTargetingEngine`: `target_volatility=0.15`, `realized_volatility` at annualized scale
   - **These three are disconnected systems. Their conventions are NOT shared.**

10. **Final classification:** `CONDITIONAL — CONTRACT CHANGE REQUIRED`

---

## 2. GOVERNANCE / SCOPE

**Authorized:** FP-3B discovery only.  
**Forbidden:** All production Python file modifications, test modifications, configuration changes, any implementation of FP-3.

---

## 3. COMPLETE VOLATILITY INVENTORY

### 3.1 Feature Platform — Registered Features (Connected)

#### 3.1.1 `atr` (Feature ID: `feat-atr-v1`)

| Attribute | Value |
|---|---|
| **Registration** | `DEFAULT_FEATURE_DEFINITIONS` in `feature_platform/orchestrator.py` L94–97 |
| **Transformer** | `AtrTransformer(window=14)` in `feature_platform/transformers.py` L44–64 |
| **Formula** | `rolling_mean(TrueRange, 14)` where `TrueRange = max(high-low, abs(high-prev_close), abs(low-prev_close))` |
| **Input data** | `high`, `low`, `close` columns in OHLCV DataFrame |
| **Timeframe** | 1-minute bars |
| **Lookback** | 14 bars |
| **Units** | Price (USD) — absolute dollar range per bar |
| **Annualized** | NO |
| **Warm-up** | 14 bars |
| **NaN handling** | `.fillna(0.0)` |
| **Zero handling** | Implicitly: `tr.rolling(14).mean()` — zero if all TR are zero |
| **Consumers** | `NormalizedAtrTransformer` (input), `ExitEngineOrchestrator` (via Feature Platform query) |
| **Tests** | `test_feature_platform.py` L128 (`atr` < `normalized_atr` in execution plan) |
| **Config** | None |
| **Status** | CONNECTED — active registered feature |
| **Volatility role** | Intermediate computation. Not directly consumable as volatility by position sizing (price units). |

#### 3.1.2 `normalized_atr` (Feature ID: `feat-natr-v1`)

| Attribute | Value |
|---|---|
| **Registration** | `DEFAULT_FEATURE_DEFINITIONS` in `feature_platform/orchestrator.py` L141–144 |
| **Transformer** | `NormalizedAtrTransformer("atr", "close")` in `feature_platform/transformers.py` L67–77 |
| **Formula** | `atr / (close + 1e-10)` — ATR divided by current price |
| **Input data** | `atr` column (computed by `AtrTransformer`), `close` column |
| **Timeframe** | 1-minute bars (ATR window = 14 bars) |
| **Lookback** | 14 bars (inherited from ATR) |
| **Units** | Dimensionless fraction (e.g., 0.005–0.025 for 1-minute BTC bars) |
| **Annualized** | NO |
| **Warm-up** | 15 bars (14 for ATR + 1 bar shift) |
| **NaN handling** | `.fillna(0.0)` |
| **Zero handling** | `(close + 1e-10)` prevents division by zero |
| **Consumers** | `ExitEngineOrchestrator` (L133: `query_realtime(["atr", "normalized_atr", "risk_score"], [symbol])`); `RiskScoreTransformer` (input) |
| **Tests** | `test_exit_engine.py` L294 seeds `normalized_atr=0.01`; `test_feature_platform.py` L162 verifies column exists after compute |
| **Config** | None |
| **Status** | CONNECTED — active registered feature with working transformer and active consumer |
| **Volatility role** | Used in `ExitEngineOrchestrator` as volatility exit threshold: `if norm_atr_val > config.volatility_threshold → exit`. ExitEngine model field: `"Volatility exit threshold on normalized ATR"`. This is the ONLY place in the codebase where `normalized_atr` is explicitly labelled as a "volatility threshold" in production code. |

#### 3.1.3 `rolling_std` (Feature ID: `feat-rolling-std-v1`)

| Attribute | Value |
|---|---|
| **Registration** | `DEFAULT_FEATURE_DEFINITIONS` in `feature_platform/orchestrator.py` L136–139 |
| **Transformer** | `RollingStdTransformer("log_return", window=20)` in `feature_platform/transformers.py` L32–41 |
| **Formula** | `rolling_std(log(close/close_prev), 20)` |
| **Input data** | `log_return` feature (which depends on `close`) |
| **Timeframe** | 1-minute bars |
| **Lookback** | 20 bars |
| **Units** | Per-bar standard deviation of log returns — dimensionless but very small (0.0005–0.005 for 1-minute crypto) |
| **Annualized** | NO |
| **Warm-up** | 21 bars (1 for log_return + 20 for rolling std) |
| **NaN handling** | `.fillna(0.0)` |
| **Zero handling** | `fillna(0.0)` only. If no variance, returns 0.0. |
| **Consumers** | NONE found in production code. Test: `test_feature_platform.py` L122 includes it in execution plan test only. |
| **Tests** | Execution plan topology test only. No functional consumer test. |
| **Config** | None |
| **Status** | CONNECTED — registered, transformer exists, but has NO production consumer. It is a dead feature in the current codebase. |
| **Volatility role** | Registered under subcategory `"Derived"`. Is the mathematically closest analog to conventional realized volatility (returns-based std). But: per-bar scale (not annualized). Not consumed by any production component. |

#### 3.1.4 `risk_score` (Feature ID: `feat-risk-score-v1`)

| Attribute | Value |
|---|---|
| **Registration** | `DEFAULT_FEATURE_DEFINITIONS` in `feature_platform/orchestrator.py` L157–161 |
| **Transformer** | `RiskScoreTransformer("normalized_atr", window=50)` in `feature_platform/transformers.py` L80–95 |
| **Formula** | `zscore(normalized_atr, 50) = (normalized_atr - rolling_mean(normalized_atr, 50)) / (rolling_std(normalized_atr, 50) + 1e-10)` |
| **Input data** | `normalized_atr` feature |
| **Timeframe** | 1-minute bars |
| **Lookback** | 50 bars |
| **Units** | Z-score (standard deviations). Typical range: -3 to +3. Mean ≈ 0. |
| **Annualized** | NO |
| **Warm-up** | 65 bars (15 for normalized_atr + 50 for z-score rolling) |
| **NaN handling** | `.fillna(0.0)` |
| **Zero handling** | `std + 1e-10` prevents division by zero |
| **Consumers** | `ExitEngineOrchestrator` (L133, L236–238) — `if risk_score_val > config.risk_score_threshold → exit` |
| **Status** | CONNECTED — active, consumed by ExitEngine for regime-based exits |
| **Volatility role** | Regime indicator, NOT absolute volatility level. Measures whether current normalized_atr is statistically high or low relative to its own recent history. NOT suitable for position sizing formula `equity × (target_vol / vol)`. |

### 3.2 Feature Platform — Not Registered (Disconnected)

#### 3.2.1 `VolatilityEngine.realized_vol` (`market_intelligence/core/analysis/volatility.py`)

| Attribute | Value |
|---|---|
| **Formula** | `std(pct_returns, window=20)` — population std (ddof=0) |
| **Input data** | Per-bar close prices, rolling 20-bar window |
| **Timeframe** | Candle timeframe (symbol+interval pair) |
| **Units** | Per-bar std of percentage returns (dimensionless, e.g., 0.005–0.05 per bar) |
| **Annualized** | NO |
| **Consumers** | `VolatilityUpdated` event published; `market_intelligence.tests.test_sprint5` validates `>= 0.0`. No production consumer found in `research_platform/`. |
| **Connected to FP** | NO — independent class, publishes to EventBus but not to FeatureStore |
| **Connected to position sizing** | NO |
| **Status** | DISCONNECTED from Feature Platform and position sizing |

#### 3.2.2 `VolatilityEngine.atr` (`market_intelligence/core/analysis/volatility.py`)

| Attribute | Value |
|---|---|
| **Formula** | Wilder's EMA-smoothed ATR: `(prev_atr × 13 + TR) / 14` after first 14 bars |
| **Units** | Price units (absolute) |
| **Connected to FP** | NO |
| **Status** | DISCONNECTED |

#### 3.2.3 `VolatilityEngine.hist_vol` (log return std)

| Attribute | Value |
|---|---|
| **Formula** | `std(log_returns, window=20)` — population std (ddof=0) |
| **Annualized** | NO |
| **Connected to FP** | NO |
| **Status** | DISCONNECTED |

#### 3.2.4 `analytics/position_sizing/sizing.py` — `volatility_adjusted_sizing`

| Attribute | Value |
|---|---|
| **Parameter docstring** | `asset_volatility: float  # annualized standard deviation fraction (e.g. 0.3 for 30%)` |
| **Formula** | `Qty = (Equity × Target_Risk_Pct) / (Asset_Volatility × Price)` |
| **Units** | Annualized std fraction (e.g. 0.20 = 20%/year) |
| **Annualized** | YES — explicitly documented |
| **Test** | `tests/unit/analytics/test_position_sizing.py` — uses `asset_volatility=0.2` (20%) |
| **Connected to live trading** | NO — parallel module in `analytics/` package. No import from `research_platform/`. |
| **Status** | DISCONNECTED from live trading pipeline |

#### 3.2.5 Portfolio Factor Model (`research_platform/portfolio_engine/factor_model.py`)

| Attribute | Value |
|---|---|
| **Formula** | `vol = float(asset_ret.std() × np.sqrt(252.0))` |
| **Label** | `"Volatility (annualized std)"` — explicit comment |
| **Units** | Annualized std of daily returns |
| **Annualized** | YES — `sqrt(252)` applied explicitly |
| **Status** | DISCONNECTED from position sizing. Analytics only. |

#### 3.2.6 `backtesting_engine/analytics/performance_metrics.py`

| Attribute | Value |
|---|---|
| **Formula** | `volatility = sample_std × math.sqrt(ctx.annualization_factor)` where `annualization_factor=252` |
| **Units** | Annualized std of daily returns |
| **Annualized** | YES — `sqrt(252)` applied via `annualization_factor` |
| **Status** | DISCONNECTED from position sizing. Backtesting analytics only. |

#### 3.2.7 `research_platform/portfolio_construction/volatility_targeting.py`

| Attribute | Value |
|---|---|
| **Formula** | `scale = target_volatility / realized_volatility` |
| **Default target_volatility** | `0.15` (15%) |
| **Test values of realized_volatility** | `0.18`, `0.30` (annualized scale) |
| **Leverage cap** | `min(2.0, scale)` — EXPLICIT |
| **Status** | DISCONNECTED from position sizing. Portfolio construction only. |

#### 3.2.8 `research_platform/portfolio_intelligence/rebalancer.py`

| Attribute | Value |
|---|---|
| **Formula** | `leverage_scale = target_volatility / portfolio_volatility` |
| **Default target_volatility** | `0.12` (12%) |
| **Leverage cap** | `min(leverage_scale, 1.5)` — EXPLICIT |
| **Status** | DISCONNECTED from position sizing. Portfolio rebalancing only. |

#### 3.2.9 `research_platform/price_action/orchestrator.py` — PA ATR

| Attribute | Value |
|---|---|
| **Formula** | `SMA(TrueRange, 14)` — simple moving average |
| **Units** | Price (USD) — absolute |
| **Connected to FP** | NO |
| **Normalized** | NO — raw price unit |
| **Status** | DISCONNECTED from Feature Platform and from position sizing |

---

## 4. POSITION SIZING CONTRACT TRACE

### 4.1 Full Execution Path

```
Environment Variable: TARGET_VOLATILITY (default: "0.10")
    ↓
SizingConfig.target_volatility = float(os.getenv("TARGET_VOLATILITY", "0.10"))
    ↓ (research_platform/position_sizing/orchestrator.py L42)
PositionSizingOrchestrator._config.target_volatility = 0.10
    ↓
calculate_size(symbol, direction) — method == "volatility"
    ↓
    vol = 0.02  [hardcoded default, comment: "default to 0.02 (2% daily)"]
    ↓
    if FeaturePlatformOrchestrator exists:
        df = fp_orch.query_realtime(["volatility"], [symbol])
        if df is not None and not df.empty and "volatility" in df.columns:
            vol = float(df.iloc[0]["volatility"])
    ↓
    [CURRENT PRODUCTION STATE: "volatility" is NOT registered → df is ALWAYS empty → vol stays at 0.02]
    ↓
    vol_safe = max(vol, 0.001)  [min guard]
    target_capital = equity × (self._config.target_volatility / vol_safe)
    raw_qty = target_capital / price
    ↓
    [NO LEVERAGE CAP applied here — distinct from VolatilityTargetingEngine and PortfolioRebalancer]
    ↓
Exposure Caps:
    A. Symbol Exposure Cap:   final_qty capped at equity × max_symbol_exposure_pct (default 0.20)
    B. Portfolio Exposure Cap: final_qty capped at remaining_exposure_budget
    C. Position Qty Cap:      final_qty ≤ max_position_qty_cap (default 1000.0)
    D. Cash Availability:     final_qty ≤ cash / price
    E. Lot Size Alignment:    round to 0.001
    ↓
SizingResult.final_qty
    ↓
PositionSizeCalculated event published
```

### 4.2 What Units Does `target_volatility` Have?

**PROVEN FROM SOURCE:**
- `target_volatility = 0.10` is a Python `float` with no type annotation, no unit comment, no docstring.
- The field in `SizingConfig` has no description: `target_volatility: float = 0.10` (models.py L20)
- The environment variable is `TARGET_VOLATILITY` with no documentation in `.env.example`
- The env template does not mention this variable at all

**INFERENCE (labelled):**
- INFERENCE: The fallback `vol = 0.02` is the only in-source clue. The comment "2% daily" suggests `vol` is daily volatility. If `vol` is daily, `target_volatility = 0.10` would be 10% daily target — a very high daily volatility target.

**What the source proves:**
- `target_volatility / vol` must be dimensionally consistent for the ratio to be meaningful
- Both must be in the same units
- The source does NOT establish what those units are for `target_volatility` independently

### 4.3 Is There a Leverage Cap in `PositionSizingOrchestrator`?

**NO.** The code at L161–199 applies ONLY capital exposure caps:
- Symbol exposure cap (20% of equity by default)
- Portfolio exposure cap (50% of equity by default)
- Position quantity cap (1000 units by default)
- Cash availability check

None of these is equivalent to the `min(2.0, scale)` or `min(1.5, scale)` leverage caps found in `VolatilityTargetingEngine` and `PortfolioRebalancer`. The exposure cap limits how much capital is deployed but does NOT prevent a large `raw_qty` from being computed before capping.

**Are exposure caps equivalent to leverage caps?**

No. An exposure cap says: "the final position's notional value ≤ X% of equity." A leverage cap on the formula says: "the scale factor ≤ X before applying to equity." The exposure cap is applied AFTER raw_qty is computed. With a 5× leverage scale and 50% portfolio cap:
- `raw_qty = equity × 5 / price` — computed at 5×
- `final_qty` is then reduced to `(equity × 0.50) / price` — 1× effective exposure
So the cap does limit final deployed exposure, but `raw_qty` still shows 5× and is logged/reported as such.

### 4.4 Environment Overrides Documented?

- `TARGET_VOLATILITY`: Exists in `orchestrator.py` L42 as an env var. **NOT documented in `.env.example`**.
- `POSITION_SIZING_METHOD`: Referenced in `orchestrator.py` L36. **NOT documented in `.env.example`**.
- Both variables have code-level defaults (`0.10` and `"fixed_risk"` respectively).
- **Conclusion:** No operator documentation for these variables exists in the repository.

### 4.5 Risk Parity Method Trace

```python
elif method == "risk_parity":
    vol = 0.02  # same fallback, no comment here
    if FeaturePlatformOrchestrator exists:
        df = fp_orch.query_realtime(["volatility"], [symbol])  # same phantom query
        if df is not None and not df.empty and "volatility" in df.columns:
            vol = float(df.iloc[0]["volatility"])
    
    vols_dict = {symbol: vol, "baseline": 0.02}
    weights = self._risk_parity.calculate_weights(vols_dict)  # inverse vol weighting
    weight = weights.get(symbol, 0.5)
    allocated_capital = equity × weight
    raw_qty = allocated_capital / price
```

`RiskParityAllocator.calculate_weights`: `Weight_i = (1/vol_i) / Sum(1/vol_j)`.

With `vol = 0.02` and `baseline = 0.02`: both equal, so `weight = 0.5`. `allocated_capital = equity × 0.5 = 50,000`. This is consistently 50% of equity. Risk parity is also currently always in fallback mode — same phantom `"volatility"` query never resolves.

---

## 5. BACKTESTING VOLATILITY CONVENTION

### 5.1 Backtesting Engine Volatility Definition

**Source:** `backtesting_engine/analytics/models/analytics.py`

```python
annualization_factor: float = Field(
    default=252.0,
    description="Periods per year for annualizing daily/periodic returns."
)
volatility: float = Field(
    default=0.0,
    description="Annualized return standard deviation / volatility."
)
```

**Formula** (`backtesting_engine/analytics/performance_metrics.py` L64–67):
```python
variance = sum((r - mean_ret) ** 2 for r in daily_returns) / (n - 1)
sample_std = math.sqrt(variance)
volatility = sample_std * math.sqrt(ctx.annualization_factor)
```

**Convention:** Volatility = sample standard deviation of periodic returns × √(annualization_factor). Default: `√252`.

### 5.2 Timeframe Assumption

The `annualization_factor = 252` implies the input `daily_returns` are **daily returns** (one return per trading day). The output `volatility` is **annualized**, expressed as a fraction (e.g., 0.15 = 15%/year).

Tests confirm: `test_portfolio_analytics.py` uses `annualization_factor=252.0` and `annualization_factor=365.0`. The `365.0` case is for crypto (no weekend closures). The `252.0` case is conventional equities.

### 5.3 Is Backtesting Volatility Convention Shared with Position Sizing?

**NO.** PROVEN FROM SOURCE:

- `backtesting_engine/` and `research_platform/position_sizing/` have no shared import.
- `PositionSizingOrchestrator` does not import from `backtesting_engine`.
- `AnalyticsContext` is not used by position sizing.
- The backtesting engine is a separate package used for offline analysis.
- The position-sizing `vol` (0.02 "daily") is numerically incompatible with annualized vol at 0.10–0.30 range.

**PROVEN:** Backtesting volatility convention = annualized daily returns std. Position sizing fallback = "2% daily" (per-bar std of daily returns). These are different systems with different conventions.

---

## 6. PORTFOLIO/RISK VOLATILITY CONVENTION

### 6.1 `PortfolioRebalancer` (`research_platform/portfolio_intelligence/rebalancer.py`)

- `target_volatility = 0.12` (12%)
- `portfolio_volatility` input is a float passed at call time (not queried from FP)
- Test values: `0.18`, `0.30` — consistent with annualized vol
- Leverage cap: `min(leverage_scale, 1.5)` — EXPLICIT
- **NOT connected to `PositionSizingOrchestrator`**. Called separately.

### 6.2 `VolatilityTargetingEngine` (`research_platform/portfolio_construction/volatility_targeting.py`)

- `target_volatility = 0.15` (15%) default
- `realized_volatility` parameter — not sourced from FP
- Formula: `scale = target_volatility / realized_volatility`, cap `min(2.0, scale)`
- **NOT connected to `PositionSizingOrchestrator`**.

### 6.3 `RiskParityAllocator` (`research_platform/portfolio_intelligence/risk_parity.py`)

- Formula: `Weight_i = (1/vol_i) / Sum(1/vol_j)`
- No unit assumption in code. Accepts any dimensionless float.
- Fallback inside: `0.01` for zero/negative vols

### 6.4 Risk Engine (`risk_engine/core/orchestrator.py`)

- Uses `sqrt(252)` for Sharpe/Sortino annualization (L654–661)
- Processes `TradingContext` via `IRiskEngine.evaluate()`
- Does NOT consume Feature Platform volatility features directly
- Does NOT interact with `PositionSizingOrchestrator` directly

### 6.5 Are These Systems Connected?

**PROVEN FROM SOURCE: NO.** The portfolio construction, portfolio intelligence, and risk engine modules are separate. `PositionSizingOrchestrator` does not import or consume any of their volatility definitions. The three `target_volatility` implementations (0.10, 0.12, 0.15) are hardcoded defaults in independent classes.

---

## 7. FEATURE PLATFORM VOLATILITY INVENTORY

| Feature Name | Registration | Formula | Units | Annualized | Warm-up | Consumers | Status |
|---|---|---|---|---|---|---|---|
| `atr` | `feat-atr-v1` | `mean(TR, 14)` | Price (USD) | NO | 14 bars | `NormalizedAtrTransformer`, `ExitEngine` | ACTIVE |
| `normalized_atr` | `feat-natr-v1` | `atr / (close + 1e-10)` | Dimensionless | NO | 15 bars | `ExitEngineOrchestrator` (volatility exit threshold) | ACTIVE |
| `rolling_std` | `feat-rolling-std-v1` | `std(log_return, 20)` | Per-bar log-return std | NO | 21 bars | **NONE in production** | REGISTERED, NO CONSUMER |
| `risk_score` | `feat-risk-score-v1` | `zscore(normalized_atr, 50)` | Z-score (std devs) | NO | 65 bars | `ExitEngineOrchestrator` | ACTIVE |
| `"volatility"` | NOT REGISTERED | N/A | N/A | N/A | N/A | `PositionSizingOrchestrator` (phantom query fails) | **PHANTOM — DOES NOT EXIST** |

**Key observation:** `rolling_std` is the most conventional returns-based volatility measure in the FP registry, but it has zero production consumers and produces per-bar values at a scale incompatible with `target_volatility=0.10` without an annualization factor.

---

## 8. PRICE ACTION VOLATILITY INVENTORY

### 8.1 PA ATR (`research_platform/price_action/orchestrator.py`)

| Attribute | Value |
|---|---|
| **Formula** | `SMA(TrueRange, 14)` where `TR = max(H-L, |H-prev_close|, |L-prev_close|)` |
| **Units** | Price (USD) — absolute dollar range |
| **Timeframe** | 1-minute OHLCV bars |
| **Lookback** | 14 bars |
| **API** | `get_atr(symbol: str) → float` |
| **Consumers** | `AISignalGenerator` (SL/TP calculation: `atr × 1.5`, `atr × 2.0`) |
| **Connected to FP** | NO — PA uses its own internal state |
| **Normalized** | NO — raw price units |
| **Intentional as volatility?** | INFERENCE: Used for SL/TP scaling (volatility-sensitive stop distances), but not labelled as "realized volatility" for position sizing. |

**PROVEN:** PA ATR is consumed by `AISignalGenerator` for stop-loss placement (`entry - atr × 1.5` for LONG). It is NOT used by `PositionSizingOrchestrator`. It is NOT normalized. It is NOT a dimensionless ratio.

### 8.2 Does PA Expose a Canonical Volatility Contract?

**NO.** PA ATR is price-denominated. It cannot be fed directly to `equity × (target_volatility / atr)` because `target_volatility` is dimensionless (0.10) while `atr` is in price units (e.g., 500 USD for BTC). The ratio would be `0.10 / 500 = 0.0002` → near-zero position, not a useful sizing signal.

---

## 9. MATHEMATICAL COMPARISON

### 9.1 Position Sizing Formula (Exact)

```
vol_safe       = max(vol, 0.001)
target_capital = equity × (target_volatility / vol_safe)
raw_qty        = target_capital / price

Expanded:
raw_qty = (equity × target_volatility) / (vol × price)

Which is equivalent to:
raw_qty = equity / price × (target_volatility / vol)
        = (1 unit of position at full equity) × leverage_scale
        where leverage_scale = target_volatility / vol
```

**Dimensional requirement:** `Units(target_volatility) = Units(vol)` for leverage_scale to be dimensionless and meaningful. If they differ in timeframe, leverage_scale is not a valid ratio.

### 9.2 Candidate Analysis

#### Candidate A: `normalized_atr`

| Attribute | Analysis |
|---|---|
| **Formula** | `SMA(TR,14) / close` |
| **Units** | Dimensionless (same unit class as target_volatility fraction) |
| **Timeframe** | 1-minute ATR. This is NOT returns-based. |
| **Mathematical distinction** | ATR measures price range, not log return dispersion. These are related but different volatility measures. |
| **Scale** | For BTC at ~50,000 with 1-minute ATR ~500: `normalized_atr = 500/50000 = 0.01`. Range: 0.005–0.025. |
| **Compatible with target_volatility=0.10?** | Arithmetically: `0.10 / 0.010 = 10× leverage`. The formula accepts it. |
| **Required conversion** | None — already dimensionless. |
| **Mathematical justification** | Range-based volatility proxy. Related to `σ × price × scaling_factor` under certain distributional assumptions, but the relationship is NOT established by any source in this repository. |
| **Leverage implications** | `0.10 / 0.010 = 10×`, `0.10 / 0.020 = 5×`, `0.10 / 0.005 = 20×` |
| **Danger level** | MEDIUM — produces leverage, no leverage cap in PositionSizingOrchestrator. Exposure caps limit final deployment. |
| **Is it conventional "volatility"?** | NO — it is an ATR ratio, not a returns std. It is widely used as a VOLATILITY PROXY in algorithmic trading, but the source does not establish this equivalence mathematically. |

#### Candidate B: `rolling_std`

| Attribute | Analysis |
|---|---|
| **Formula** | `std(log_return, 20)` |
| **Units** | Per-1-minute-bar log return std |
| **Timeframe** | 1-minute bars |
| **Mathematical distinction** | This IS conventional statistical returns volatility — but per-bar, not annualized. |
| **Scale** | For 1-minute BTC bars: typical ~0.0005–0.005. |
| **Compatible with target_volatility=0.10?** | ONLY with an explicit timeframe conversion. Without it: `0.10 / 0.001 = 100× leverage`. DANGEROUS. |
| **Required conversion** | To make compatible with "daily" scale: multiply by `sqrt(1440)` ≈ 37.9. But NO such conversion factor is established by any source in this repository. |
| **Leverage implications (raw, NO conversion)** | `0.10 / 0.001 = 100×`, `0.10 / 0.005 = 20×`, `0.10 / 0.0005 = 200×` |
| **Danger level** | **CRITICAL** — produces catastrophic leverage without an annualization step. |
| **Can be used directly?** | NO. Not without an explicit, source-supported conversion factor. |

#### Candidate C: PA ATR (raw)

| Attribute | Analysis |
|---|---|
| **Units** | Price (USD) |
| **Compatible?** | NO — `target_volatility / atr_usd` is not dimensionally valid. `0.10 / 500 = 0.0002` → trivial position. |
| **Required conversion** | Division by price (= normalized ATR). But then it becomes Candidate A. |
| **Verdict** | **REJECTED** — price units. |

#### Candidate D: New Dedicated `VolatilityTransformer`

| Attribute | Analysis |
|---|---|
| **What it would do** | Compute `rolling_std(log_return) × sqrt(N)` where `N` is an explicit annualization factor |
| **Status** | NOT AUTHORIZED — would require new production code. Deferred. |
| **Would it solve the problem?** | YES — it could produce a semantically unambiguous, documentable unit with a clear relationship to `target_volatility`. |
| **Verdict** | DEFERRED — cannot be implemented in FP-3B |

---

## 10. LEVERAGE SAFETY ANALYSIS

### 10.1 Current Fallback Leverage (PROVEN)

```
vol             = 0.02  (hardcoded fallback, comment: "2% daily")
target_vol      = 0.10  (default)
leverage_scale  = 0.10 / 0.02 = 5.0
target_capital  = equity × 5.0
raw_qty         = target_capital / price

Example (equity=100,000, BTC@50,000):
  raw_qty = (100,000 × 5.0) / 50,000 = 10 BTC
  exposure = 10 × 50,000 = 500,000 (5× equity)
```

**Symbol exposure cap (default 20%):** `max_symbol_exposure = 100,000 × 0.20 = 20,000`  
`final_qty = 20,000 / 50,000 = 0.4 BTC` — exposure capped to 1/5 of raw_qty.

**Portfolio exposure cap (default 50%):** `50,000 budget`  
`final_qty = 50,000 / 50,000 = 1.0 BTC` — capped.

**Conclusion:** Raw calculation is 5× leverage. Exposure caps reduce final deployed exposure to at most 50% of equity. The caps work, but `raw_qty = 10.0` is still the logged value. Any analysis of the sizing log would see 5× leverage as the formula's intent.

### 10.2 Leverage with `normalized_atr` (CALCULATED)

Using test-evidenced value `normalized_atr = 0.01` (`test_exit_engine.py` L294):

```
vol             = 0.010
target_vol      = 0.10
leverage_scale  = 0.10 / 0.010 = 10×
target_capital  = equity × 10 = 1,000,000
raw_qty         = 1,000,000 / 50,000 = 20 BTC
exposure        = 20 × 50,000 = 1,000,000 (10× equity)

After symbol cap (20%): final_qty = 0.4 BTC ($20,000)
After portfolio cap (50%): final_qty = 1.0 BTC ($50,000)
```

**Switching to `normalized_atr` would double the raw leverage** from 5× to 10× in typical conditions. The exposure caps still limit deployed exposure to the same amount (50% of equity maximum). **The FINAL position size would be identical** due to capping — but the raw formula now shows 10× intent rather than 5×.

### 10.3 Leverage with `rolling_std` (CALCULATED — WITHOUT ANY CONVERSION)

Using representative value `rolling_std = 0.001` for 1-minute BTC bars:

```
vol             = 0.001
target_vol      = 0.10
leverage_scale  = 0.10 / 0.001 = 100×
target_capital  = equity × 100 = 10,000,000
raw_qty         = 10,000,000 / 50,000 = 200 BTC

After symbol cap (20%): final_qty = 0.4 BTC ($20,000)
After portfolio cap (50%): final_qty = 1.0 BTC ($50,000)
```

**Final capped qty is identical**, but `raw_qty = 200 BTC` would be computed and logged. The sizing result would report `raw_qty=200.0, final_qty=1.0`. This is internally inconsistent, auditorially alarming, and indicates the formula is operating in a non-meaningful regime.

### 10.4 Existing Leverage Caps Elsewhere (for comparison)

| Component | Leverage Cap | Source |
|---|---|---|
| `VolatilityTargetingEngine` | `min(2.0, scale)` | `portfolio_construction/volatility_targeting.py` L24 |
| `PortfolioRebalancer` | `min(leverage_scale, 1.5)` | `portfolio_intelligence/rebalancer.py` L37 |
| `PositionSizingOrchestrator` | **NONE on formula** | Only exposure caps post-computation |

**PROVEN:** Two of three leverage-based sizing components in the repository have explicit formula-level leverage caps. `PositionSizingOrchestrator` does NOT.

---

## 11. CANDIDATE DECISION MATRIX

| Candidate | Formula | Timeframe | Units | Scale | Target Compatibility | Leverage (raw) | Max Leverage Cap | Recommendation Rank |
|---|---|---|---|---|---|---|---|---|
| `normalized_atr` | `SMA(TR,14)/close` | 1-minute ATR | Dimensionless | 0.005–0.025 | Partial — same unit class, 10× at typical val | 10×–20× | NONE in formula | **B — Conditional** |
| `rolling_std` | `std(log_ret, 20)` | 1-minute log-ret | Per-bar std | 0.0005–0.005 | **UNSAFE without conversion** | 20×–200× | NONE | **C — REJECTED** |
| PA ATR (raw) | `SMA(TR,14)` | 1-minute | Price (USD) | 100–5000 | INCOMPATIBLE (price units) | — | N/A | **C — REJECTED** |
| New `VolatilityTransformer` | `rolling_std × sqrt(N)` | Configurable | Configurable | Configurable | YES — designable | Configurable | Designable | **D — Requires New Contract** |
| `market_intel realized_vol` | `std(pct_ret, 20)` | Per-bar | Per-bar std | 0.005–0.05 | Same scale issue as rolling_std | 2×–20× | NONE | **C — REJECTED** (disconnected) |

---

## 12. CANONICAL VOLATILITY RECOMMENDATION

**Outcome:** `CONDITIONAL — CONTRACT CHANGE REQUIRED`

**Rationale:**

No existing Feature Platform feature satisfies all three conditions simultaneously:
1. Correct mathematical unit for the sizing formula
2. Semantically documented timeframe alignment with `target_volatility=0.10`
3. Safe leverage range without introducing undefined-scale risks

`normalized_atr` is the leading candidate because:
- It is registered, computed, and has an active consumer already using it as a "volatility threshold" (`ExitEngineOrchestrator`)
- It is dimensionless — the same unit class as `target_volatility`
- It requires only a query-key change (no new transformer, no new DAG node)
- Its range (0.005–0.025) is compatible with the current fallback's intent (`vol=0.02`)

However, making `normalized_atr` canonical requires an explicit contract decision:

**CONTRACT CHANGE REQUIRED:** `target_volatility = 0.10` must be re-evaluated and possibly reconfigured to match the `normalized_atr` scale. At `normalized_atr ≈ 0.010` (typical), `leverage = 10×`. If the intent is a lower leverage target (e.g., 2×), `target_volatility` should be set to approximately `0.010 × 2 = 0.020`. This is a configuration change, not a code change, but it requires CTO decision.

`rolling_std` requires rejection from direct use until an explicit, source-documented timeframe conversion factor is defined — none currently exists in the repository.

---

## 13. PROPOSED CONTRACT

Status annotations: **[PROVEN]** = derived from source evidence. **[PROPOSED]** = not yet established. **[UNKNOWN]** = insufficient evidence.

| Contract Field | Value | Status |
|---|---|---|
| **Feature name** | `normalized_atr` | [PROVEN — registered in FP] |
| **Mathematical definition** | `SMA(TrueRange, 14) / (close + 1e-10)` | [PROVEN — from transformers.py L77] |
| **Input data** | `atr` (computed), `close` columns in OHLCV DataFrame | [PROVEN] |
| **Timeframe** | 1-minute bars | [PROVEN — `required_resolution="1m"` in FeatureRecord] |
| **Lookback** | 14 bars (ATR window) | [PROVEN] |
| **Units** | Dimensionless fraction (ATR/price ratio) | [PROVEN] |
| **Annualization** | NONE applied | [PROVEN — no sqrt factor in transformer] |
| **Warm-up** | 15 bars minimum before reliable output | [PROVEN — 14 ATR + 1 shift] |
| **NaN behavior** | `.fillna(0.0)` — returns 0.0 during warm-up | [PROVEN — transformers.py L77] |
| **Zero behavior** | `(close + 1e-10)` prevents zero denominator | [PROVEN] |
| **Valid range** | 0.001–0.10 under normal market conditions | [PROPOSED — based on formula semantics; no source explicitly bounds this range] |
| **Fallback** | `vol = 0.02` when Feature Platform unavailable | [PROVEN — orchestrator.py L117] |
| **Fallback semantics** | "2% daily" per source comment | [PROVEN — orchestrator.py L116 comment] |
| **target_volatility relationship** | `leverage = target_volatility / normalized_atr` | [PROPOSED — requires CTO contract approval] |
| **Target compatibility** | `target_volatility` must be calibrated to normalized_atr scale (0.005–0.025 range) | [PROPOSED] |
| **Leverage semantics** | `leverage_scale = target_volatility / normalized_atr` | [PROPOSED] |
| **Maximum leverage without cap** | Unbounded (no formula-level cap in PositionSizingOrchestrator) | [PROVEN — from code audit] |
| **Consumer query key** | `query_realtime(["normalized_atr"], [symbol])` | [PROPOSED — current key is `"volatility"`, change not yet authorized] |
| **Testing requirements** | Unit test confirming sizing formula uses normalized_atr values at expected leverage scale | [PROPOSED] |

---

## 14. PROVEN FACTS

All of the following are directly verifiable from source code:

1. `"volatility"` is NOT a registered Feature Platform feature. `DEFAULT_FEATURE_DEFINITIONS` contains no entry with `name="volatility"`. (`feature_platform/orchestrator.py` L59–169)

2. `PositionSizingOrchestrator.calculate_size()` queries `fp_orch.query_realtime(["volatility"], [symbol])`. This always returns an empty DataFrame in production. (`position_sizing/orchestrator.py` L120)

3. The fallback `vol = 0.02` is active 100% of the time in production for `method="volatility"` and `method="risk_parity"`. (`position_sizing/orchestrator.py` L117, L138)

4. The comment at L116 states: `"Check FeatureStore for volatility if available, else default to 0.02 (2% daily)"`. This is the only source-documented timeframe interpretation of `vol`.

5. The formula is: `target_capital = equity × (target_volatility / max(vol, 0.001))`. No timeframe conversion or annualization factor is applied. (`position_sizing/orchestrator.py` L124)

6. `normalized_atr` is registered (`feat-natr-v1`), computed via `NormalizedAtrTransformer`, and actively consumed by `ExitEngineOrchestrator` for volatility-based exit decisions. (`exit_engine/orchestrator.py` L133–234; `exit_engine/models.py` L19: `"Volatility exit threshold on normalized ATR"`)

7. `rolling_std` is registered (`feat-rolling-std-v1`), computed via `RollingStdTransformer(window=20)`, but has NO production consumer. (`feature_platform/feature_pipeline.py` L42)

8. `analytics/position_sizing/sizing.py` explicitly documents `asset_volatility` as `"annualized standard deviation fraction (e.g. 0.3 for 30%)"`. This module is NOT used by the live trading pipeline. (`analytics/position_sizing/sizing.py` L25)

9. `VolatilityTargetingEngine` and `PortfolioRebalancer` both use `target_volatility / realized_volatility` with explicit leverage caps (`min(2.0, scale)` and `min(1.5, scale)`). `PositionSizingOrchestrator` has NO equivalent leverage cap. (`portfolio_construction/volatility_targeting.py` L24; `portfolio_intelligence/rebalancer.py` L37)

10. The backtesting engine computes `volatility = sample_std × sqrt(252.0)`. This is DISCONNECTED from the position-sizing formula. (`backtesting_engine/analytics/performance_metrics.py` L67)

11. `TARGET_VOLATILITY` and `POSITION_SIZING_METHOD` are NOT documented in `.env.example`.

12. The unit test `test_position_sizing_volatility` seeds `vol=0.05`, sets `target_volatility=0.10`, and asserts `raw_qty=20.0` (equity=100,000, price=10,000). Comment: `"Leverage scale = 0.10 / 0.05 = 2.0x"`. The test makes no statement about what timeframe `vol=0.05` represents. (`research_platform/tests/test_position_sizing.py` L97–121)

---

## 15. UNKNOWNS

| # | Unknown | Blocking? |
|---|---|---|
| U-1 | Is `target_volatility = 0.10` intended as 10% daily, 10% annualized, or purely a dimensionless leverage-scale numerator at `normalized_atr` scale? The source does not establish this explicitly. | **YES** |
| U-2 | Is the fallback comment "2% daily" intended as per-trading-day returns std, or as ATR/price ratio on a daily bar? The code uses 1-minute bars; "daily" is ambiguous without specifying whether it means "1 calendar day" or "the bar timeframe". | **YES** |
| U-3 | What `POSITION_SIZING_METHOD` value is active in production? If `method="fixed_risk"` (the default), neither the volatility formula nor `normalized_atr` matters at all currently. | MEDIUM |
| U-4 | Is 5×–20× raw leverage (before exposure caps) acceptable by TOJI risk policy? The source does not define a maximum raw leverage limit for `PositionSizingOrchestrator`. | **YES** |
| U-5 | Should `normalized_atr` be the canonical "volatility" key in FP, or should `PositionSizingOrchestrator` query `"normalized_atr"` directly? Naming affects FP governance. | MEDIUM |
| U-6 | Should a formula-level leverage cap be added to `PositionSizingOrchestrator` analogous to `min(2.0, scale)` in `VolatilityTargetingEngine`? | MEDIUM |
| U-7 | The `rolling_std` transformer exists and produces a conventional returns-based volatility, but requires an annualization factor. Is a `sqrt(1440)` (per-minute to per-day) or `sqrt(525600)` (per-minute to annualized) conversion mathematically appropriate for TOJI's use case? | CONDITIONAL |

---

## 16. RISKS

| Risk | Severity | Description |
|---|---|---|
| **Phantom feature remains unresolved** | HIGH | `"volatility"` query will continue to silently fail, and vol=0.02 fallback will remain. Position sizing is already broken at the feature-resolution layer. |
| **normalized_atr at wrong scale** | MEDIUM-HIGH | If `target_volatility=0.10` is confirmed at 10× leverage intent, but is mis-calibrated to the normalized_atr range, position sizes will be systematically wrong by an order of magnitude. |
| **No leverage cap** | HIGH | `PositionSizingOrchestrator` has no formula-level leverage cap. The two parallel portfolio modules with the same formula DO have caps. This inconsistency means a very small `vol` value (e.g., during quiet market conditions) would produce extreme `raw_qty` values, limited only by the exposure caps. |
| **Undocumented env vars** | MEDIUM | `TARGET_VOLATILITY` and `POSITION_SIZING_METHOD` not in `.env.example`. Any operator deployment uses code defaults (10% and "fixed_risk" respectively). |
| **rolling_std safety** | CRITICAL | If `rolling_std` is ever mapped to the volatility query without a conversion factor, leverage of 100×–200× would be computed (though capped by exposure limits). |
| **Convention divergence** | MEDIUM | Three separate `target_volatility` implementations at 0.10, 0.12, 0.15 with different leverage caps create an inconsistent risk posture across the codebase. |

---

## 17. WHAT MUST NOT BE IMPLEMENTED YET

The following changes are explicitly BLOCKED until CTO authorization:

- Modifying `PositionSizingOrchestrator` to query `"normalized_atr"` instead of `"volatility"`
- Adding any leverage cap to `PositionSizingOrchestrator`
- Registering a `"volatility"` alias in the Feature Platform
- Creating a new `VolatilityTransformer` or `AnnualizedVolatilityTransformer`
- Changing `target_volatility = 0.10` default or env var value
- Changing the `vol = 0.02` fallback
- Applying any `sqrt()` conversion to `rolling_std`
- Modifying `rolling_std`, `normalized_atr`, or `atr` transformers
- Starting FP-4, FP-5, or any subsequent sprint stage

---

## 18. EXACT NEXT STAGE RECOMMENDATION

**Recommended action:** CTO must resolve U-1 and U-4 before FP-3 implementation can proceed.

**Specifically, CTO must explicitly choose one of:**

> **Decision A:** `target_volatility = 0.10` is intended at the `normalized_atr` scale (0.005–0.025 range). Typical leverage of 5×–20× before exposure caps is accepted. Approved to map `PositionSizingOrchestrator` to query `"normalized_atr"`.

> **Decision B:** `target_volatility = 0.10` is a miscalibrated value. The intent is a leverage target of approximately N×. `target_volatility` will be reconfigured to `N × typical_normalized_atr` (e.g., for 2× target: `target_volatility = 0.020`). Approved to map to `"normalized_atr"` with config change.

> **Decision C:** `target_volatility = 0.10` is intended as an annualized volatility fraction. A per-bar-to-annualized scaling factor must be defined before `rolling_std` can be used. A new `VolatilityTransformer` computing annualized returns-based vol is required. FP-3 implementation remains blocked until the new transformer design is approved.

> **Decision D:** HOLD — insufficient evidence. Do not implement FP-3 until further research is commissioned.

After Decision A or B: FP-3 implementation consists of changing one line in `PositionSizingOrchestrator` (query key: `"volatility"` → `"normalized_atr"`), potentially updating `target_volatility` env var, and writing/updating a unit test.

---

## 19. PRODUCTION FILES MODIFIED

```
Production Python files modified: 0
Test files modified:              0
Configuration files modified:     0
Environment files modified:       0
```

---

## 20. FINAL GATE CLASSIFICATION

```text
╔════════════════════════════════════════════════════════════════════════════════╗
║                                                                                ║
║   SPRINT-004 FP-3B CANONICAL VOLATILITY DISCOVERY GATE:                        ║
║                                                                                ║
║   CONDITIONAL — CONTRACT CHANGE REQUIRED                                       ║
║                                                                                ║
║   REASON:                                                                      ║
║   The repository contains a viable canonical candidate (normalized_atr)        ║
║   that is:                                                                     ║
║     • Already registered in Feature Platform                                   ║
║     • Already consumed by ExitEngine as a volatility threshold                 ║
║     • Dimensionally compatible with the sizing formula                         ║
║     • The closest existing feature to the fallback "2% daily" vol              ║
║                                                                                ║
║   However, implementation requires CTO resolution of:                          ║
║     1. Is target_volatility=0.10 intended at normalized_atr scale?             ║
║     2. Is 5×–20× raw formula leverage acceptable before exposure caps?         ║
║     3. Should target_volatility be reconfigured for the normalized_atr range?  ║
║                                                                                ║
║   HARD REJECTIONS (PROVEN):                                                    ║
║     • rolling_std: REJECTED — 20×–200× leverage without conversion.           ║
║     • PA ATR (raw): REJECTED — price units, incompatible.                      ║
║     • market_intel realized_vol: REJECTED — disconnected from FP.              ║
║                                                                                ║
║   LEADING CANDIDATE: normalized_atr (Rank B — Conditional)                    ║
║                                                                                ║
║   MINIMUM IMPLEMENTATION SCOPE (once approved):                                ║
║     • 1 line change: query key "volatility" → "normalized_atr"                 ║
║     • Optional: reconfigure target_volatility env var                          ║
║     • 1 unit test update / addition                                            ║
║                                                                                ║
║   Production Files Modified: 0                                                 ║
║   Test Files Modified: 0                                                       ║
║   Configuration Modified: 0                                                    ║
║                                                                                ║
║   STOP. Awaiting CTO Decision A, B, C, or D from Section 18.                  ║
║                                                                                ║
╚════════════════════════════════════════════════════════════════════════════════╝
```

---

**STOP.** FP-3B discovery gate is complete. Awaiting CTO authorization before any production implementation.
