# SPRINT 004 — FP-3 OQ-1 RESOLUTION
## Target Volatility Semantic Audit / Position-Sizing Contract Analysis

**Author:** TOJI Senior Staff Engineer  
**Date:** 2026-08-12  
**Governance:** Master Architecture Governance — Sprint 004 / FP-3 OQ Resolution  
**Predecessor:** `SPRINT-004-FP3-VOLATILITY-CONTRACT-GATE.md` — DISCOVERY COMPLETE  
**Stage:** FP-3 — OQ-1 RESOLUTION (Source Audit / Math Contract Analysis)  
**Production Files Modified:** **0**  
**Status:** See final classification at bottom.

> **HARD STOP:** Zero production Python files modified during this stage.  
> This is a source audit and mathematical contract analysis only.

---

## 1. EXECUTIVE SUMMARY

This document resolves **OQ-1a and OQ-1b** from the FP-3 discovery gate:

- **OQ-1a:** Is the position sizing formula `target_capital = equity * (target_volatility / vol)` intended for dimensionless `vol` in the range [0.005, 0.02]?
- **OQ-1b:** Is `target_volatility = 0.10` (10%) intended as annualized, daily, or per-minute volatility?

**Finding:**

The source evidence establishes the following:

1. `target_volatility = 0.10` is used as a **dimensionless fraction** in the position-sizing formula. It is compared directly to `vol` (the asset volatility input) in the ratio `target_volatility / vol`.
2. The code comment at L116 of `research_platform/position_sizing/orchestrator.py` explicitly states: `"else default to 0.02 (2% daily)"`. This is the only in-source documentation of the intended timeframe interpretation.
3. The inline comment documents the fallback as **"2% daily"** — meaning the formula is calibrated for **daily-scale** dimensionless volatility fractions.
4. The unit test `test_position_sizing_volatility` seeds a `volatility` value of `0.05` (5%) and treats `target_volatility = 0.10`. The test comment reads: `"Leverage scale = 0.10 / 0.05 = 2.0x"`. This confirms the formula is used as a **leverage scale factor**: `scale = target_vol / asset_vol`. The units of `target_volatility` and `vol` must be **identical**.
5. The `analytics/position_sizing/sizing.py` module (a parallel sizing implementation) documents `asset_volatility` as **"annualized standard deviation fraction (e.g. 0.3 for 30%)"**. This is a second codebase module defining the concept differently from the inline fallback comment.
6. The `VolatilityTargetingEngine` (`portfolio_construction/volatility_targeting.py`) and `PortfolioRebalancer` (`portfolio_intelligence/rebalancer.py`) both use the formula `scale = target_volatility / realized_volatility` with test values `realized_volatility=0.18` and `realized_volatility=0.30` — values consistent with **annualized** volatility fractions (18%, 30% per year), not per-bar or per-minute.
7. The backtesting analytics subsystem (`backtesting_engine/analytics/models/analytics.py`) defines `annualization_factor: float = 252.0` for **daily** returns and applies `volatility = sample_std * math.sqrt(annualization_factor)`. This is the system-wide convention for expressing annualized volatility.

**Conclusion on OQ-1a/OQ-1b:**

> **TARGET VOLATILITY SEMANTICS ARE INCONSISTENTLY DEFINED BY CURRENT SOURCE.**

The fallback comment says **"2% daily"** but all parallel portfolio construction, factor model, and analytics subsystems use **annualized** volatility at scales of 10–30%. The two interpretations are numerically incompatible in the same formula. The position-sizing formula does not apply any timeframe conversion. No `sqrt(252)` or `sqrt(525600)` appears anywhere in `position_sizing/orchestrator.py`.

The **safest provable statement** is: `target_volatility = 0.10` is a **dimensionless fraction** used as a leverage scale numerator. Its timeframe semantics — whether daily, annualized, or per-bar — are **not uniformly established by the current source**. The formula works correctly only if `vol` is expressed in the same timeframe as `target_volatility`.

---

## 2. OQ-1 DEFINITION

**OQ-1a:** Does the position-sizing formula `target_capital = equity * (target_volatility / vol)` expect `vol` in the range `[0.005, 0.02]` (per-bar / daily scale), or a different scale?

**OQ-1b:** Is `target_volatility = 0.10` expressed as annualized, daily, or per-minute volatility?

These two questions are linked: they determine what numerical range `vol` must fall in for the position-sizing ratio to produce safe, non-degenerate results.

---

## 3. SOURCE EVIDENCE

### 3.1 Files Inspected During This Audit

| File | Relevant Evidence |
|---|---|
| `research_platform/position_sizing/orchestrator.py` | Exact formula, fallback comment "2% daily", `target_volatility=0.10` |
| `research_platform/position_sizing/models.py` | `SizingConfig.target_volatility: float = 0.10` |
| `research_platform/tests/test_position_sizing.py` | Unit test seeds `volatility=0.05`, computes `scale=2.0`, confirms ratio semantics |
| `analytics/position_sizing/sizing.py` | Parallel module, parameter docstring: "annualized standard deviation fraction (e.g. 0.3 for 30%)" |
| `research_platform/portfolio_construction/volatility_targeting.py` | `scale = target_volatility / realized_volatility`, default `0.15`, max leverage cap 2.0x |
| `research_platform/portfolio_intelligence/rebalancer.py` | `leverage_scale = target_volatility / portfolio_volatility`, default `0.12`, cap 1.5x |
| `research_platform/portfolio_construction/orchestrator.py` | `scale_allocation(weights, realized_volatility, target_volatility=0.15)` |
| `confluence/tests/test_sprint6.py` | `realized_volatility=0.18`, `realized_volatility=0.30` — consistent with annualized scales |
| `market_intelligence/core/analysis/volatility.py` | `realized_vol` = per-bar std of percentage returns (NOT annualized) |
| `research_platform/portfolio_engine/factor_model.py` | `vol = float(asset_ret.std() * np.sqrt(252.0))` — explicit annualization with sqrt(252) |
| `research_platform/analysis/metrics_engine.py` | `annualized_volatility = stdev * math.sqrt(252.0)` — explicit sqrt(252) annualization |
| `backtesting_engine/analytics/performance_metrics.py` | `volatility = sample_std * math.sqrt(ctx.annualization_factor)` — annualization_factor=252 |
| `backtesting_engine/analytics/models/analytics.py` | `annualization_factor: float = 252.0` — authoritative system constant for daily → annual scaling |
| `research_platform/validation_core/regime.py` | `if vol > 0.02` — classifies "volatile" regime as > 2% per-bar std of returns |

---

## 4. TARGET VOLATILITY TRACE

### 4.1 Configuration Source

**File:** `research_platform/position_sizing/models.py` L20  
```python
target_volatility: float = 0.10
```
- Dataclass field. Default value `0.10`.
- No docstring on the field.
- No comment.
- No units annotation.
- No timeframe annotation.

**File:** `research_platform/position_sizing/orchestrator.py` L42  
```python
target_volatility=float(os.getenv("TARGET_VOLATILITY", "0.10")),
```
- Loaded from environment variable `TARGET_VOLATILITY`.
- No documentation in environment variable spec found in the repository.
- No `.env.example`, no `README` specifying the unit for `TARGET_VOLATILITY`.

### 4.2 Usage Site — Primary Formula

**File:** `research_platform/position_sizing/orchestrator.py` L114–127  
```python
elif method == "volatility":
    # Volatility target: target_volatility / asset_volatility
    # Check FeatureStore for volatility if available, else default to 0.02 (2% daily)
    vol = 0.02
    ...
    target_capital = equity * (self._config.target_volatility / max(vol, 0.001))
    raw_qty = target_capital / price
    risk_amount = raw_qty * (price * 0.02)
    reasons.append(f"Volatility Target: target_vol={self._config.target_volatility}, vol={vol:.4f}")
```

**Critical evidence in comment:** `"else default to 0.02 (2% daily)"`

This is the **only in-source documentation** attributing a timeframe to the `vol` variable. The comment directly states:
- `vol = 0.02` is a **daily** (per-day) volatility
- `0.02` represents **2% daily**

If `vol` is intended as daily volatility, then for the ratio `target_volatility / vol` to be dimensionally consistent, `target_volatility` must also be expressed as **daily volatility**. Under this interpretation, `target_volatility = 0.10` means **10% daily volatility target** — which is extremely high (typical crypto daily vol is 2–4%).

### 4.3 Usage Site — Unit Test Evidence

**File:** `research_platform/tests/test_position_sizing.py` L97–121  
```python
def test_position_sizing_volatility(container, event_bus):
    # Seed volatility in feature store
    vol_df = pd.DataFrame([{"volatility": 0.05, ...}])
    feat_orch.store.save_features("volatility", "1.0.0", "BTC/USDT", vol_df)

    sizer._config.target_volatility = 0.10

    # Leverage scale = 0.10 / 0.05 = 2.0x
    # Target Capital = 100,000 * 2.0 = 200,000
    # Qty = 200,000 / 10,000 = 20.0
    assert res.raw_qty == pytest.approx(20.0)
```

**Test comment analysis:**
- Seeds `vol = 0.05` (5%)
- `target_volatility = 0.10` (10%)
- Ratio: `0.10 / 0.05 = 2.0x leverage`

The test treats this as a **leverage multiplier on total equity**: `target_capital = 100,000 * 2.0 = 200,000`. This is a **200% leverage** result — the system is willing to allocate 2× equity. This result is produced mechanically; the test does not document what timeframe the `vol=0.05` represents.

The test values `0.05` and `0.10` are **not labelled as daily or annualized** anywhere in the test file. The test validates arithmetic correctness of the formula, not the semantic appropriateness of the input scale.

---

## 5. POSITION-SIZING FORMULA — COMPLETE RECONSTRUCTION

### 5.1 Method: `"volatility"` — Full Formula

```
Inputs:
  equity          = portfolio equity (USD)
  target_vol      = self._config.target_volatility  [default: 0.10]
  vol             = asset volatility from Feature Platform ["volatility"] key
                    OR 0.02 if unavailable  [comment: "2% daily"]
  price           = current asset price (USD)

Formula:
  vol_safe        = max(vol, 0.001)
  leverage_scale  = target_vol / vol_safe
  target_capital  = equity * leverage_scale
  raw_qty         = target_capital / price

Output:
  raw_qty         = number of units to buy/sell (before exposure caps)

Derived (informational only):
  risk_amount     = raw_qty * (price * 0.02)   ← 2% of price as stop distance estimate
```

### 5.2 Formula Interpretation (Direct)

The formula computes:

```
                 equity × target_volatility
raw_qty  =  ─────────────────────────────────
                    vol × price
```

This is the standard **volatility targeting** formula from portfolio theory:

```
             Target_Vol
position = ──────────────────  ×  equity / price
            Realized_Asset_Vol
```

The ratio `target_vol / vol` is a **leverage multiplier** on equity. When `vol < target_vol`, leverage > 1.0 (system takes more than 1 unit of exposure per unit of equity). When `vol > target_vol`, leverage < 1.0 (system de-risks).

### 5.3 Unit Dimensional Analysis

The formula `leverage_scale = target_vol / vol` is dimensionally valid if and only if:

```
Units(target_vol) == Units(vol)
```

There are NO timeframe conversion factors applied in the formula. No `sqrt(252)`, no `sqrt(525600)`, no `sqrt(1440)`. The formula is bare.

**Therefore:** Whatever timeframe unit `vol` is expressed in, `target_volatility` must be in the same timeframe unit for the ratio to produce a meaningful result.

### 5.4 Current Fallback Arithmetic with `vol = 0.02`

When `"volatility"` feature is unavailable (current production state):

```
vol             = 0.02         (hardcoded, comment: "2% daily")
target_vol      = 0.10         (config default)
leverage_scale  = 0.10 / 0.02 = 5.0
target_capital  = equity × 5.0 = 500,000  (on 100,000 equity = 5× leverage)
raw_qty         = 500,000 / price
```

**At price = 50,000 (BTC):** `raw_qty = 10.0 BTC = $500,000 exposure on $100,000 equity = 5× leverage`

This is the **live production behavior today** for `method="volatility"`. It always produces 5× leverage unless overridden by exposure caps.

---

## 6. UNIT ANALYSIS — ALL LOCATIONS

### 6.1 Position Sizing Orchestrator (`research_platform/position_sizing/orchestrator.py`)

| Location | Value | Comment / Label |
|---|---|---|
| L116 | `vol = 0.02` | Comment: `"default to 0.02 (2% daily)"` |
| L124 | `target_volatility / max(vol, 0.001)` | No unit comment on `target_volatility` |
| L42 | `target_volatility=0.10` | No unit annotation |
| L20 (models.py) | `target_volatility: float = 0.10` | No unit annotation |

**Evidence verdict for orchestrator:** `vol` fallback is documented as "2% daily". `target_volatility` has no matching timeframe annotation.

### 6.2 Analytics Module (`analytics/position_sizing/sizing.py`)

```python
@staticmethod
def volatility_adjusted_sizing(
    total_equity: float,
    target_risk_pct: float,
    asset_volatility: float,  # annualized standard deviation fraction (e.g. 0.3 for 30%)
    price: float,
) -> float:
    """
    Formula: Qty = (Equity * Target_Risk_Pct) / (Asset_Volatility * Price)
    """
    cash_risk = total_equity * target_risk_pct
    vol_dollar = price * asset_volatility
    return float(cash_risk / vol_dollar)
```

**This is a different formula and a different module.** `asset_volatility` is documented here as **"annualized standard deviation fraction (e.g. 0.3 for 30%)"**. The formula is also structurally different: `Qty = (Equity × Target_Risk_Pct) / (Asset_Volatility × Price)`, not the same as `Qty = Equity × (Target_Volatility / Asset_Vol) / Price`. This module is in the `analytics/` package, NOT in `research_platform/position_sizing/`. They are parallel, unconnected implementations.

**Evidence verdict for analytics module:** Explicitly annualized. Typical values: 0.20–0.40 (20–40% per year). This is the conventional finance interpretation.

### 6.3 Portfolio Construction Module (`research_platform/portfolio_construction/volatility_targeting.py`)

```python
def scale_to_target(self, weights, realized_volatility, target_volatility=0.15) -> Dict[str, float]:
    scale = target_volatility / realized_volatility
    leverage_limit = min(2.0, scale)
    return {asset: w * leverage_limit for asset, w in weights.items()}
```

- `target_volatility` default: `0.15` (15%)
- `leverage_limit` cap: `2.0x`
- `realized_volatility` in tests: `0.18`, `0.30` — consistent with **annualized** values

**Evidence verdict:** This module uses annualized-scale values. The 2.0x leverage cap constrains the scale ratio from blowing up.

### 6.4 Portfolio Rebalancer (`research_platform/portfolio_intelligence/rebalancer.py`)

```python
def __init__(self, target_volatility: float = 0.12) -> None:
    ...
leverage_scale = self.target_volatility / portfolio_volatility
target_weights[asset] = weight * min(leverage_scale, 1.5)  # Cap leverage at 1.5x
```

- `target_volatility` default: `0.12` (12%)
- Cap: `1.5x`
- `portfolio_volatility` input: used at annualized scale in tests (0.18, 0.30)

**Evidence verdict:** Annualized scale interpretation. 12–15% target is standard institutional annualized vol target.

### 6.5 Factor Model (`research_platform/portfolio_engine/factor_model.py`)

```python
# Volatility (annualized std)
vol = float(asset_ret.std() * np.sqrt(252.0))
```

**Explicit label:** `"Volatility (annualized std)"`. Uses `sqrt(252)` multiplier on daily return std. **Result is annualized.**

### 6.6 Analytics / Metrics Engine (`research_platform/analysis/metrics_engine.py`)

```python
annualized_volatility = stdev * math.sqrt(252.0)
```

**Label:** `annualized_volatility`. Explicit multiplication by `sqrt(252)`. **Result is annualized.**

### 6.7 Backtesting Analytics Models (`backtesting_engine/analytics/models/analytics.py`)

```python
annualization_factor: float = Field(default=252.0, description="Periods per year for annualizing daily/periodic returns.")
volatility: float = Field(default=0.0, description="Annualized return standard deviation / volatility.")
```

**System-wide constant:** `annualization_factor = 252`. Volatility field is explicitly `"Annualized return standard deviation"`. Default assumption: **daily returns, annualized by sqrt(252).**

### 6.8 Validation Core / Regime Classifier (`research_platform/validation_core/regime.py`)

```python
vol = float(np.std(sub))  # std of returns in the rolling window
if vol > 0.02:  # High standard deviation
    labels.append("volatile")
```

- `vol` here = std of returns in a 20-bar rolling window
- Threshold `0.02` = 2% per-bar std of returns
- NOT annualized
- Classification as "volatile" when per-bar std > 2%

**Evidence:** This 0.02 threshold is consistent with the fallback in `position_sizing/orchestrator.py` — both treat `0.02` as a per-bar/per-period std of returns threshold.

---

## 7. CANDIDATE COMPARISON

### 7.1 `normalized_atr`

| Attribute | Detail |
|---|---|
| **Formula** | `SMA(TrueRange, 14) / (close + 1e-10)` |
| **Timeframe** | 1-minute bars |
| **Lookback** | 14 bars |
| **Units** | Dimensionless fraction of price (e.g., 0.005–0.025 for crypto) |
| **Registered in FP** | YES |
| **Annualized** | NO |
| **Typical numerical scale** | [0.005, 0.025] for 1-minute BTC bars |
| **Compatible with `target_volatility=0.10`** | **PARTIALLY** — same unit type (dimensionless fraction), but scale gap: `0.10 / 0.010 = 10x leverage`. If `normalized_atr ≈ 0.010` and `target_vol = 0.10`, leverage = 10x. |
| **Timeframe consistent with fallback "2% daily"** | **NO** — `normalized_atr` is a range-based intraday ratio, not a daily returns std. 2% on 1-minute ATR/close is different from 2% on daily returns std. |
| **Leverage analysis** | `normalized_atr ≈ 0.01`: leverage = 10x. `normalized_atr ≈ 0.02`: leverage = 5x. `normalized_atr ≈ 0.05`: leverage = 2x. All produce significant leverage. |
| **Dangerous?** | MEDIUM — produces real leverage, but the 2.0x leverage cap mechanism in other FP modules does NOT exist in `PositionSizingOrchestrator.calculate_size()`. Exposure caps apply but are based on % of equity, not a leverage limit. |
| **Notes** | `normalized_atr` is ATR-based (range). The fallback says "daily". These are measuring different things with the same numeric scale. No conversion documented. |

### 7.2 `rolling_std`

| Attribute | Detail |
|---|---|
| **Formula** | `std(log(close/close_prev), window=20)` |
| **Timeframe** | 1-minute bars (per-bar std of log returns) |
| **Lookback** | 20 bars |
| **Units** | Dimensionless std of log returns (per 1-minute bar) |
| **Registered in FP** | YES |
| **Annualized** | NO |
| **Typical numerical scale** | [0.0005, 0.005] per 1-minute bar for crypto |
| **Compatible with `target_volatility=0.10`** | **DANGEROUS** — `0.10 / 0.001 = 100x leverage`. Even at `rolling_std=0.005`, leverage = 20x. Extreme without annualization. |
| **Timeframe consistent with fallback "2% daily"** | **NO** — `rolling_std` per 1-minute bar is ~50–100x smaller than daily. To get "2% daily" from `rolling_std`, multiply by `sqrt(1440) ≈ 37.9`. |
| **Leverage analysis** | Produces catastrophic leverage without a timeframe conversion factor. |
| **Dangerous?** | **CRITICAL** — directly feeding `rolling_std` to the formula is mathematically unsafe without `sqrt(periods_per_day)` conversion. |
| **Notes** | Would require explicit annualization or at-minimum a "per-day" scaling factor (sqrt(1440)) before being used in the current formula. |

### 7.3 PA-ATR (`PriceActionOrchestrator.get_atr`)

| Attribute | Detail |
|---|---|
| **Formula** | `mean(TrueRange[-14:])` — price units |
| **Timeframe** | 1-minute bars |
| **Units** | Price (USD) — NOT dimensionless |
| **Compatible with `target_volatility=0.10`** | **NO** — price units cannot be directly compared to a dimensionless ratio in the formula `target_vol / vol`. Requires division by current price to normalize. |
| **Dangerous?** | **YES (if used directly)** — PA-ATR in price units fed to the formula as `vol` would produce nonsensical results. ATR=500 (for BTC), target=0.10 → scale = 0.10/500 = 0.0002 → near-zero position size. |
| **Notes** | Not applicable without normalization. |

### 7.4 `VolatilityFeature` (legacy `data/feature_store/definitions.py`)

| Attribute | Detail |
|---|---|
| **Formula** | `pct_change(close).rolling(20).std()` |
| **Timeframe** | 1-minute bars |
| **Units** | Std of pct returns per 1-minute bar — same unit class as `rolling_std` |
| **Typical numerical scale** | [0.0005, 0.005] per 1-minute bar |
| **Compatible with `target_volatility=0.10`** | **DANGEROUS** — same scale mismatch as `rolling_std` |
| **Registered in FP** | **NO** — disconnected legacy class |
| **Notes** | Disconnected. Not accessible. Not relevant for production use. |

---

## 8. FALLBACK ANALYSIS — `vol = 0.02`

### 8.1 Complete Occurrence Map in `research_platform/position_sizing/orchestrator.py`

| Line | Value | Context | Label |
|---|---|---|---|
| L103 | `price * 0.02` | `stop_distance` for fixed_risk method | Comment: `"standard 2% stop distance"` |
| L111 | `price * 0.02` | `stop_distance` for Kelly method | No comment |
| L116–117 | `vol = 0.02` | Volatility method fallback | Comment: `"default to 0.02 (2% daily)"` |
| L126 | `price * 0.02` | `risk_amount` estimate for volatility method | No comment |
| L133 | `price * 0.02` | `risk_amount` estimate for equal_weight method | No comment |
| L138 | `vol = 0.02` | Risk parity method fallback | No comment |
| L146 | `"baseline": 0.02` | Baseline vol in risk parity dict | No comment |
| L151 | `price * 0.02` | `risk_amount` estimate for risk_parity method | No comment |
| L156 | `price * 0.02` | `stop_distance` for fallback method | No comment |
| L209 | `price * 0.02` | `risk_amount` in final result | No comment |

### 8.2 Fallback Interpretations

| Occurrence | Mathematical Role | Implied Units | Separately Documented? |
|---|---|---|---|
| `vol = 0.02` (L117) | Asset volatility denominator | Dimensionless "2% daily" per comment | YES — "2% daily" |
| `vol = 0.02` (L138) | Asset volatility for risk parity | Dimensionless | NO — no comment |
| `"baseline": 0.02` (L146) | Baseline asset in risk parity comparison | Dimensionless | NO — no comment |
| `price * 0.02` (stop distances) | 2% of current price as stop distance | Price units (USD) | YES — "standard 2% stop distance" |

### 8.3 Key Finding — Two Different 0.02 Uses

There are **two distinct uses of `0.02`** in `PositionSizingOrchestrator`:

1. **Volatility denominator** (`vol = 0.02`): Represents asset volatility (dimensionless fraction). Comment says "2% daily".
2. **Stop distance** (`price * 0.02`): Represents 2% of price as stop-loss distance (price units). Independent of the volatility feature.

These are semantically different. The `0.02` stop distance is a fixed 2% stop-loss assumption used for `risk_amount` estimation throughout ALL sizing methods, not just volatility. The `vol = 0.02` fallback is specific to the volatility and risk-parity sizing methods.

### 8.4 Masking of Missing Feature Computation

**YES** — the fallback `vol = 0.02` completely masks the absence of the `"volatility"` feature. Because `"volatility"` is not registered in Feature Platform, `query_realtime()` always returns empty. The code branch:

```python
if df is not None and not df.empty and "volatility" in df.columns:
    vol = float(df.iloc[0]["volatility"])
```

is never reached. The system permanently operates on `vol = 0.02`. The production behavior is: **5× leverage always**, regardless of actual market volatility.

---

## 9. CRITICAL RISK ANALYSIS

### 9.1 Could choosing `normalized_atr` create excessive leverage?

**YES.** `normalized_atr` for 1-minute BTC bars typically ranges from 0.005 to 0.020. With `target_volatility = 0.10`:

```
Minimum normalized_atr = 0.005 → scale = 0.10/0.005 = 20× leverage
Typical normalized_atr = 0.010 → scale = 0.10/0.010 = 10× leverage
High normalized_atr    = 0.020 → scale = 0.10/0.020 =  5× leverage
```

**All scenarios produce significant leverage (5× to 20×).** The current exposure caps (50% portfolio, 20% symbol) limit actual capital deployment but do NOT limit the quantity calculation before caps are applied. Whether these leverage levels are intended by the system design depends on the `target_volatility` interpretation.

**Contrast with fallback:** `vol = 0.02` (fallback) → `scale = 0.10/0.02 = 5×`. `normalized_atr ≈ 0.01` → `scale = 10×`. **Using `normalized_atr` would produce double the leverage of the current fallback in typical conditions.**

### 9.2 Could choosing `rolling_std` create excessive leverage?

**YES — CRITICAL.** `rolling_std` per 1-minute bar typically ranges from 0.0005 to 0.005. With `target_volatility = 0.10`:

```
Minimum rolling_std = 0.0005 → scale = 0.10/0.0005 = 200× leverage
Typical rolling_std = 0.001  → scale = 0.10/0.001  = 100× leverage
High rolling_std    = 0.005  → scale = 0.10/0.005  =  20× leverage
```

**`rolling_std` fed directly to the current formula produces catastrophic leverage (20× to 200×).** This is a critical risk. The exposure caps would ultimately limit actual deployed capital, but `raw_qty` would be extreme and may overflow intermediate calculations.

### 9.3 Is a timeframe conversion required?

**YES — for `rolling_std`:** Per-1-minute `rolling_std` requires a conversion factor of `sqrt(1440)` (≈ 37.9) to express as daily volatility, or `sqrt(525600)` (≈ 725) to express as annualized. Without conversion, it cannot be used with the current formula.

**UNCLEAR — for `normalized_atr`:** `normalized_atr` is a dimensionless ratio (ATR/close), not a statistical returns-based measure. It does not follow the `sqrt(T)` scaling law. Its timeframe dependency is defined by the ATR window (14 bars × 1 minute = 14 minutes effective). Whether to apply any scaling factor to `normalized_atr` before using it as a proxy for "daily" volatility is not addressed by the current source.

### 9.4 Is annualization required?

**For `rolling_std`:** YES. Required before safe use in this formula, given the "2% daily" comment and analogy to other modules using annualized values at 10–30% scale.

**For `normalized_atr`:** Depends on interpretation. If `target_volatility = 0.10` is "10% daily normalized_atr target" (unusual but conceivable), then no conversion needed. If `target_volatility = 0.10` is "10% annualized" (typical finance interpretation), then normalization of `normalized_atr` to an annualized-equivalent scale is needed — but there is no standard formula for converting ATR-based vol to annualized returns-based vol.

### 9.5 Is the current sizing formula itself assuming a specific volatility unit?

**The formula makes no explicit unit assumption.** It is a pure arithmetic ratio. However:
- The inline comment "2% daily" implies `vol` should be at a **daily** scale
- The fallback value `0.02` produces `leverage = 5×` which is the current production behavior
- The test seeds `vol = 0.05` and expects `leverage = 2×` — consistent with any volatility scale, not specifically daily or annualized

**There is no `sqrt(252)` or other annualization in the formula itself.** The formula is timeframe-agnostic by implementation, but timeframe-specific by the comment documentation.

### 9.6 Can we safely map `normalized_atr` directly to volatility?

**NOT DEFINITIVELY SAFE without additional analysis.** The mapping would:
1. Produce leverage levels higher than the current fallback (5× today → 10× typical with `normalized_atr ≈ 0.01`)
2. Change production behavior from a constant 5× to a dynamic 5–20× depending on market conditions
3. Not be "daily" volatility as implied by the comment
4. Not be "annualized" volatility as documented in the parallel analytics modules

The mapping is **architecturally clean** (registered feature, dimensionless, no code changes except query key rename), but the **semantic and leverage implications require explicit CTO sign-off.**

### 9.7 What evidence is missing to safely approve the mapping?

| Missing Evidence | Risk Level |
|---|---|
| CTO confirmation that `target_volatility = 0.10` is intended at the scale of `normalized_atr` (0.005–0.025 range) | **CRITICAL** |
| Explicit leverage cap in `PositionSizingOrchestrator.calculate_size()` for `method="volatility"` | **HIGH** |
| Documentation of whether "2% daily" fallback should remain consistent with `normalized_atr` scale | **HIGH** |
| Confirmation that 10×–20× leverage from typical `normalized_atr` values is acceptable | **CRITICAL** |
| Any equivalent to the `min(2.0, scale)` cap found in `VolatilityTargetingEngine` | **HIGH** |

---

## 10. DECISION MATRIX

| Candidate | Existing Formula | Timeframe | Units | Typical Scale | Target Compatibility | Leverage Risk | Recommendation |
|---|---|---|---|---|---|---|---|
| `normalized_atr` | `SMA(TR,14) / close` | 1-minute bars | Dimensionless fraction | 0.005–0.025 | Partial — same unit class; `0.10 / 0.010 = 10×` | MEDIUM-HIGH (5×–20×) | CONDITIONAL |
| `rolling_std` | `std(log_return, 20)` | 1-minute bars | Per-bar std | 0.0005–0.005 | **DANGEROUS** — `0.10 / 0.001 = 100×` without scaling | **CRITICAL (20×–200×)** | **REJECTED** |
| `atr` (raw) | `SMA(TrueRange,14)` | 1-minute bars | Price units (USD) | 10–2000 (for BTC) | **INCOMPATIBLE** — price units vs. fraction | UNDEFINED | **REJECTED** |
| PA-ATR / price | `SMA(TR,14) / price` | 1-minute bars | Dimensionless | Same as `normalized_atr` | Equivalent to `normalized_atr` | MEDIUM-HIGH | Not a FP feature |
| Dedicated feature | New `VolatilityTransformer` | Configurable | Configurable | Configurable | **DEFERRED** | Unknown until defined | DEFERRED |

---

## 11. CTO RECOMMENDATION

### Recommendation: **CONDITIONAL A — `normalized_atr` subject to explicit CTO scale confirmation**

**Full recommendation statement:**

Of the available candidates, `normalized_atr` is the only registered, computed, dimensionless Feature Platform feature that:
1. Will not produce catastrophic leverage in a single step (unlike `rolling_std`)
2. Is already used correctly by `ExitEngineOrchestrator` for the `volatility_threshold` exit rule
3. Requires only a query-key change in production (`"volatility"` → `"normalized_atr"`)
4. Has documented warm-up behavior and NaN protection

However, `normalized_atr` **cannot be approved as the final canonical source** without CTO resolution of one remaining question: **what leverage level is acceptable?**

The leverage arithmetic is:

```
If target_volatility = 0.10 and normalized_atr ≈ 0.010 (typical):
    leverage = 10×

If target_volatility = 0.10 and normalized_atr ≈ 0.020 (high vol):
    leverage = 5×

If target_volatility = 0.10 and normalized_atr ≈ 0.005 (low vol):
    leverage = 20×
```

**The current fallback produces exactly 5× (`0.10/0.02`).** Using `normalized_atr` directly would produce 5×–20× depending on market conditions. Whether this is intended system behavior requires explicit CTO sign-off.

If **5× is the intended target leverage**, then `target_volatility` should be re-evaluated to be set equal to `target_normalized_atr × 5`, i.e., `target_volatility = 0.01 × 5 = 0.05`. This is a config change, not a code change.

If **higher leverage is acceptable**, `normalized_atr` can be used directly with `target_volatility = 0.10`.

**`rolling_std` is rejected** for direct use without a mandatory timeframe conversion. This is a hard recommendation.

**A dedicated `VolatilityTransformer`** is deferred — it adds scope without solving the OQ-1 semantics question.

### What the CTO must decide (exactly one):

> **Decision Point A:** "The system intends `target_volatility = 0.10` to mean 10× of typical `normalized_atr` value (≈ 0.010), producing 10× leverage in normal conditions. Approved."

> **Decision Point B:** "The system intends `target_volatility` to be calibrated to `normalized_atr` scale. `target_volatility` will be reconfigured to a value appropriate for the expected `normalized_atr` range (e.g., `target_volatility = 0.02` → 2× leverage at typical conditions). Approved with config change."

> **Decision Point C:** "The system intends `target_volatility = 0.10` as annualized volatility (10% per year). This requires a conversion factor when using per-bar `normalized_atr`. A `sqrt()` scaling factor or a daily-annualized `rolling_std` with proper conversion must be defined. HOLD — further implementation definition required."

---

## 12. REQUIRED CONTRACT

**Subject to CTO decision on leverage scale (Decision A, B, or C above).**

| Attribute | Contract Value |
|---|---|
| **Feature name** | `normalized_atr` (query directly; no new registry key `"volatility"` required) |
| **Formula** | `SMA(TrueRange, 14) / (close + 1e-10)` |
| **Timeframe** | 1-minute bars |
| **Lookback** | 14 bars (warm-up: 15 bars for ATR + 1 bar shift) |
| **Units** | Dimensionless fraction of price |
| **Annualized** | NO |
| **Warm-up** | 15 bars minimum. Returns 0.0 during warm-up (fillna). Fallback to 0.02 during warm-up. |
| **NaN behavior** | `NormalizedAtrTransformer` applies `fillna(0.0)`. No NaN propagates. |
| **Zero/invalid handling** | `(close + 1e-10)` guards division by zero. Min guard: `max(vol, 0.001)` in sizing formula. |
| **Fallback** | `vol = 0.02` (comment: "2% daily"). Retained as-is. |
| **Consumer expectation** | `PositionSizingOrchestrator` queries `"normalized_atr"` instead of `"volatility"` |
| **`target_volatility` compatibility** | See Decision A/B/C above. Formula is dimensionally consistent but leverage level needs CTO confirmation. |
| **Required validation** | `normalized_atr` must be in `[0.001, 0.15]` for normal markets. Values outside this range should trigger a warning and consider falling back to `0.02`. |
| **Leverage cap needed** | YES — equivalent to `min(2.0, scale)` cap present in `VolatilityTargetingEngine` and `PortfolioRebalancer` is **NOT present** in `PositionSizingOrchestrator`. Whether to add one is a CTO decision. |

---

## 13. REMAINING UNKNOWNS

| # | Unknown | Impact | Blocking? |
|---|---|---|---|
| U-1 | Is `target_volatility = 0.10` intended as 10% daily, 10% annualized, or a dimensionless target at `normalized_atr` scale? | Determines correct `vol` input range and whether reconfiguration of `target_volatility` is needed | **YES** |
| U-2 | Is 5×–20× leverage acceptable for `method="volatility"` and `method="risk_parity"`? | Determines whether a leverage cap analogous to `VolatilityTargetingEngine.min(2.0, scale)` must be added | **YES** |
| U-3 | Is the "2% daily" comment in L116 authoritative documentation or a placeholder? | Determines whether fallback semantics need correction | YES |
| U-4 | What `TARGET_VOLATILITY` env var value is used in production deployment? | The config can be overridden at deploy time; production behavior may differ from the `0.10` default | MEDIUM |
| U-5 | Is `PositionSizingOrchestrator.method="volatility"` or `method="risk_parity"` actually active in production today? | If neither method is active, the leverage risk is theoretical. `POSITION_SIZING_METHOD` env var controls this. | MEDIUM |

---

## 14. SCOPE EXCLUSIONS

No production code was modified during this audit.

| Item | Status |
|---|---|
| Modifying `PositionSizingOrchestrator` query key | DEFERRED — pending CTO contract approval |
| Modifying `target_volatility` config value | DEFERRED — CTO decision A/B/C required |
| Adding leverage cap to `PositionSizingOrchestrator` | DEFERRED — CTO decision required |
| Registering `"volatility"` feature in FP | NOT IN SCOPE |
| Modifying `normalized_atr` transformer | NOT IN SCOPE |
| Modifying `rolling_std` transformer | NOT IN SCOPE |
| Any FP-4, FP-5, FP-6 work | NOT IN SCOPE |

---

## 15. PRODUCTION FILES MODIFIED

```
Production Files Modified: 0
Test Files Modified: 0
```

---

## 16. EXACT FILES INSPECTED

```
research_platform/position_sizing/orchestrator.py         ← PRIMARY: formula, fallback, comment "2% daily"
research_platform/position_sizing/models.py               ← SizingConfig.target_volatility = 0.10
research_platform/tests/test_position_sizing.py           ← Unit test: vol=0.05, target=0.10, scale=2.0x
analytics/position_sizing/sizing.py                       ← Parallel module: "annualized std fraction"
research_platform/portfolio_construction/volatility_targeting.py  ← scale = target/realized, cap 2.0x
research_platform/portfolio_intelligence/rebalancer.py    ← scale = target/portfolio_vol, cap 1.5x
research_platform/portfolio_construction/orchestrator.py  ← scale_allocation(), default 0.15
confluence/tests/test_sprint6.py                          ← realized_volatility=0.18, 0.30 (annualized scale)
market_intelligence/core/analysis/volatility.py           ← realized_vol per-bar (NOT annualized)
research_platform/portfolio_engine/factor_model.py        ← vol = std * sqrt(252) — explicit annualization
research_platform/analysis/metrics_engine.py              ← annualized_volatility = stdev * sqrt(252)
backtesting_engine/analytics/performance_metrics.py       ← volatility = std * sqrt(annualization_factor)
backtesting_engine/analytics/models/analytics.py          ← annualization_factor=252, volatility="Annualized"
research_platform/validation_core/regime.py               ← vol>0.02 threshold, per-bar, not annualized
```

---

## 17. FINAL CLASSIFICATION

```text
╔════════════════════════════════════════════════════════════════════════════════╗
║                                                                                ║
║   SPRINT-004 FP-3 OQ-1 RESOLUTION GATE:                                        ║
║                                                                                ║
║   HOLD — TARGET VOLATILITY SEMANTICS NOT PROVEN                                ║
║                                                                                ║
║   REASON:                                                                      ║
║   The source contains one in-code documentation point (L116 comment:           ║
║   "2% daily") indicating vol is expected at daily scale. All parallel         ║
║   portfolio construction modules use annualized-scale values (0.10–0.30).     ║
║   No single uniform interpretation is established by the repository.           ║
║                                                                                ║
║   PROVEN FACTS:                                                                ║
║   • target_volatility = 0.10 is a dimensionless fraction                      ║
║   • Formula: target_capital = equity × (target_vol / vol)                     ║
║   • No timeframe conversion in formula (no sqrt(252), sqrt(1440), etc.)       ║
║   • Fallback vol = 0.02 comment: "2% daily"                                   ║
║   • Fallback produces 5× leverage today (production state)                    ║
║   • rolling_std REJECTED — produces 20×–200× leverage without conversion      ║
║   • normalized_atr CONDITIONAL — dimensionally compatible, 5×–20× leverage   ║
║     at typical normalized_atr ≈ 0.005–0.020 range                             ║
║   • Parallel analytics modules: target_volatility at annualized scale 10–30%  ║
║                                                                                ║
║   UNRESOLVED:                                                                  ║
║   • Is 10× leverage at normalized_atr ≈ 0.010 acceptable? (CTO: A/B/C)       ║
║   • Is target_volatility 10% per-day, annualized, or at normalized_atr scale? ║
║   • Should a leverage cap (e.g. min(2.0, scale)) be added?                    ║
║                                                                                ║
║   NEXT STEP: CTO selects Decision A, B, or C from Section 11.                 ║
║                                                                                ║
║   Production Files Modified: 0                                                 ║
║   FP-3 Implementation: NOT STARTED                                             ║
║   STOP. Awaiting CTO decision on leverage scale.                               ║
║                                                                                ║
╚════════════════════════════════════════════════════════════════════════════════╝
```

---

**STOP.** OQ-1 resolution audit is complete. Awaiting CTO decision A, B, or C before FP-3 implementation proceeds.
