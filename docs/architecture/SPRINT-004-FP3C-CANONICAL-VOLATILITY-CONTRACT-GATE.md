# SPRINT 004 — FP-3C
## Canonical Volatility Contract Gate

**Author:** TOJI Senior Quant Architect  
**Date:** 2026-08-13  
**Governance:** Master Architecture Governance — Sprint 004  
**Predecessor Gate:** `SPRINT-004-FP3B-CANONICAL-VOLATILITY-DISCOVERY-GATE.md` — CONDITIONAL  
**CTO Decision:** Decision C — Investigate annualized returns-based volatility; do not map to `normalized_atr`.  
**Stage:** FP-3C — CONTRACT DEFINITION ONLY  
**Production Files Modified:** **0**  
**Test Files Modified:** **0**  
**Configuration Modified:** **0**  
**Environment Modified:** **0**

---

## 1. EXECUTIVE SUMMARY

This gate formally defines the canonical mathematical contract for TOJI's realized volatility feature, intended for consumption by `PositionSizingOrchestrator`. It does not implement anything.

**Key Conclusions:**

1. **The repository uses `252` as the universal annualization constant** across all analytics, backtesting, and portfolio modules. Not `365`. Not `525600`. `252` is the institutional default — daily trading returns, annualized. This is hardcoded in ≥15 source locations across 6 subsystems.

2. **`525600` does not appear anywhere in the repository.** [PROVEN] It is mathematically derivable (365 × 24 × 60) but has zero source support.

3. **`365` appears only in `AnalyticsContext.trading_days` for CAGR calendar arithmetic**, and in `backtesting_engine/tests` explicitly labeled as the crypto alternative to `252`. It is never used as an annualization factor for volatility calculation.

4. **The volatility formula the repository consistently uses is:** `annualized_vol = sample_std(periodic_returns) × sqrt(annualization_factor)`, where `annualization_factor` is an operator-configurable constant defaulting to `252`.

5. **The existing `rolling_std` Feature Platform feature computes `std(log_returns, window=20)` — this is the per-bar returns std without annualization.** To become a canonical annualized volatility, it requires multiplication by `sqrt(annualization_factor)`. This multiplication is NOT currently present in any FP transformer.

6. **For TOJI's 1-minute data, the correct annualization factor is NOT trivially `252` or `525600`.** TOJI ingests 1-minute bars from Binance. The question of the annualization factor depends on whether position sizing is calibrated to intraday volatility (per-minute), daily volatility, or annualized volatility. The source does not establish which is intended. [UNKNOWN]

7. **`target_volatility = 0.10` is consistent with a 10% annualized volatility target** when compared to the `VolatilityTargetingEngine` (15%) and `PortfolioRebalancer` (12%) that use annualized realized vol in the same formula pattern. This is [INFERRED], not proven.

8. **The test `test_position_sizing_volatility` seeds `vol = 0.05` and comments `"Leverage scale = 0.10 / 0.05 = 2.0x"`. No timeframe annotation is present in the test.** The test makes no statement about whether `vol=0.05` is "5% annualized", "5% daily", or any other convention.

9. **Final Classification:** `CONDITIONAL — CTO DECISION REQUIRED`

---

## 2. GOVERNANCE / SCOPE

**Authorized:** Contract definition and mathematical analysis only.  
**Forbidden (explicitly):** All production Python modifications, test modifications, configuration changes, environment variable changes, Feature Platform registration changes, transformer changes, PositionSizingOrchestrator changes, any leverage cap implementation, any sqrt formula implementation, any naming changes.

---

## 3. EXISTING VOLATILITY INVENTORY (CONDENSED FROM FP-3B)

The complete inventory is in `SPRINT-004-FP3B-CANONICAL-VOLATILITY-DISCOVERY-GATE.md`. This section summarizes the evidence relevant to FP-3C.

### 3.1 Feature Platform Volatility Features

| Feature | Formula | Units | Annualized | Warm-up |
|---|---|---|---|---|
| `rolling_std` | `std(log_return, 20)` — sample std (ddof=0 in VolatilityEngine; ddof=1 in SharpeValidator) | Per-bar log-return std | NO | 21 bars |
| `normalized_atr` | `ATR(14) / close` | Dimensionless ATR ratio | NO | 15 bars |

**Critical note:** The FP `RollingStdTransformer` uses pandas `rolling().std()` which defaults to `ddof=1` (sample std). The `VolatilityEngine.realized_vol` computes `sqrt(sum(r - mean)^2 / len(returns))` which is ddof=0 (population std). These are **different formulas**, confirmed below.

### 3.2 Annualization Constants in Codebase

**PROVEN FROM SOURCE** — all literal occurrences of annualization constants:

| Constant | Locations | Usage |
|---|---|---|
| `252` | ≥15 locations: `analytics/statistics/calculator.py` (×9), `research_platform/portfolio_analytics/risk_metrics.py` (×3), `research_platform/portfolio_intelligence/metrics.py`, `research_platform/portfolio_intelligence/analytics.py` (×2), `backtesting_engine/monte_carlo/simulator.py`, `research_platform/backtesting_engine/analytics.py`, `research_platform/alpha_factory/evaluation.py` | Daily returns annualization (252 trading days/year) |
| `365` | `AnalyticsContext.trading_days=365.0` (CAGR calendar arithmetic), `backtesting_engine/tests` (explicitly labeled "crypto alternative") | Calendar days for CAGR; crypto-appropriate alternative to 252 for backtesting |
| `525600` | **ZERO occurrences** | Not present anywhere in repository |
| `1440` | **ZERO occurrences as annualization factor** | Not present anywhere in repository |

---

## 4. MATHEMATICAL DEFINITION

### 4.1 The Candidate Formula

The CTO-nominated candidate for canonical volatility is:

```
annualized_vol = rolling_std(log_return, N) × sqrt(periods_per_year)
```

Where:
- `log_return[t] = log(close[t] / close[t-1])`
- `rolling_std` uses sample standard deviation (ddof=1)
- `N` = lookback window in bars
- `periods_per_year` = annualization factor (see Section 6)

### 4.2 Mathematical Justification

**[PROVEN]** The formula `σ_annual = σ_period × sqrt(T)` is the standard square-root-of-time scaling rule under the assumption that returns are i.i.d. (independently and identically distributed). It states: if a random process has per-period variance `σ²`, then the T-period variance is `T × σ²`, and the T-period standard deviation is `σ × sqrt(T)`.

This is EXACTLY the formula used throughout the TOJI codebase for Sharpe/Sortino/volatility annualization:
- `ann_vol = std_ret × math.sqrt(periods_per_year)` — `analytics/statistics/calculator.py` L54
- `volatility = sample_std × math.sqrt(ctx.annualization_factor)` — `backtesting_engine/analytics/performance_metrics.py` L67
- `downside_volatility = downside_std × math.sqrt(context.annualization_factor)` — `risk_metrics.py` L65
- `annual_std = std × math.sqrt(annual_factor)` — `portfolio_intelligence/metrics.py` L42

The formula is internally consistent across the entire codebase. [PROVEN]

**Assumption validity:** The i.i.d. assumption is known to be imperfect for financial returns (volatility clustering, fat tails, autocorrelation). However, all existing analytics in the repository apply this formula without adjustment, making it the established TOJI convention regardless of theoretical purity.

### 4.3 Explicit Separation: Three Different Volatility Measures

**IMPORTANT — These are mathematically distinct measures that must NOT be conflated.**

#### Measure A: `normalized_atr`
```
normalized_atr = ATR(14) / close
ATR = rolling_mean(TrueRange, 14)
TrueRange = max(H-L, |H-prev_close|, |L-prev_close|)
```
- **Nature:** Price-range-based volatility proxy. Measures the average high-low-close range over 14 bars, normalized by current price.
- **Economic interpretation:** "The typical price swing over 14 bars as a fraction of current price."
- **NOT returns-based.** Does not require the i.i.d. assumption. Cannot be directly annualized by `sqrt(T)` without additional assumptions.
- **Scale:** 0.005–0.025 for 1-minute BTC.

#### Measure B: `rolling_std` (per-bar, not annualized)
```
rolling_std = std(log_return, 20)  [ddof=1]
log_return = log(close/prev_close)
```
- **Nature:** Sample standard deviation of log returns over the last 20 bars.
- **Economic interpretation:** "The per-bar volatility of returns over the last 20 bars."
- **Units:** Per-1-minute-bar log-return standard deviation.
- **Scale:** 0.0005–0.005 for 1-minute BTC.
- **Is returns-based.** Can be annualized by `sqrt(periods_per_year)`.

#### Measure C: Annualized Realized Volatility (proposed canonical)
```
annualized_vol = rolling_std(log_return, N) × sqrt(periods_per_year)
```
- **Nature:** Per-bar rolling_std scaled to an annual basis.
- **Economic interpretation:** "The expected standard deviation of returns over one year, estimated from recent N-bar history."
- **Units:** Annualized dimensionless fraction (e.g., 0.60 = 60%/year for BTC).
- **IS annualized.** Directly comparable to `target_volatility = 0.10` if the latter is in annualized units.

**Key mathematical distinction between A and C:**
- `normalized_atr` ≠ `annualized_vol`. They correlate in regime (both increase during volatile periods) but their numerical values differ by approximately `sqrt(periods_per_year) / sqrt(14)` — a factor of roughly 194× for 1-minute to annual conversion.
- These are NOT interchangeable without an explicit, source-supported mapping.

---

## 5. TIMEFRAME DEFINITION

### 5.1 What Timeframe Does TOJI Use?

**[PROVEN]** TOJI's Feature Platform operates on 1-minute (`"1m"`) OHLCV bars. All `DEFAULT_FEATURE_DEFINITIONS` entries have `required_resolution="1m"` and `update_frequency="1m"`. Price Action also aggregates ticks into 1-minute bars.

**[PROVEN]** TOJI trades crypto assets (BTC/USDT, ETH/USDT per `.env.example` `BINANCE_SYMBOLS`).

**[PROVEN]** Crypto markets operate 24/7, 365 days per year.

### 5.2 One-Minute Bar Implications

Per 1-minute bar → what is one "period"?

- 1 minute = 1 period
- 1 hour = 60 periods
- 1 day = 1440 periods (24×60)
- 1 year (365 days) = 525,600 periods (365×24×60)
- 1 year (252 days) = 362,880 periods (252×24×60)

**If the canonical feature computes `rolling_std` on 1-minute bars, annualizing requires `sqrt(525600)` ≈ 725.** This is NOT supported by any source in the codebase.

**If the canonical feature computes `rolling_std` on DAILY bar returns (aggregated from 1-minute), annualizing requires `sqrt(365)` ≈ 19.1 (crypto) or `sqrt(252)` ≈ 15.87 (equities).** Only the `252/365` path is supported by the codebase.

### 5.3 The 1-Minute vs. Daily Ambiguity — CRITICAL

**[PROVEN]** The `VolatilityEngine` in `market_intelligence` receives candle-by-candle data and computes `realized_vol` per-candle using the candle's own timeframe (whatever `candle.interval` is). If given 1-minute candles, it produces 1-minute per-bar returns and a per-1-minute-bar std. It is NOT annualized.

**[PROVEN]** All backtesting analytics in TOJI assume `daily_returns` as the input to annualization. The field is literally named `daily_returns: List[float]` in `PerformanceMetricsEngine` and `EquityCurveAnalysis`.

**[INFERRED]** If the Feature Platform produces `rolling_std` from 1-minute bars and the codebase's annualization convention is based on "daily returns × sqrt(252)", there is a **resolution mismatch**. The rolling_std from 1-minute data should use `sqrt(525600)` not `sqrt(252)` if it is to produce the same annualized number as the daily analytics.

**[UNKNOWN]** The source does not establish whether TOJI intends:
- (a) A 1-minute rolling_std annualized with `sqrt(525600)` → yields ~0.50–3.0 for BTC (matching real-world ~80% annual vol for BTC)
- (b) A daily rolling_std annualized with `sqrt(365)` → same mathematical result but requiring daily bar aggregation
- (c) A per-1-minute rolling_std without annualization → raw value (not compatible with target_volatility=0.10 as annualized)

---

## 6. ANNUALIZATION DEFINITION

### 6.1 What the Source Uses

**[PROVEN]** The source consistently uses:
```python
annualized_vol = std_per_period × sqrt(annualization_factor)
```
where `annualization_factor` defaults to `252.0` in all 15+ occurrences.

**[PROVEN]** `AnalyticsContext` explicitly documents: `"Periods per year for annualizing daily/periodic returns."` — the word "daily" is in the description.

**[PROVEN]** The comment in `portfolio_intelligence/metrics.py` L33 states: `annual_factor = 252.0  # Daily returns assumption`.

**[PROVEN]** `backtesting_engine/tests/test_portfolio_analytics.py` L362 uses `annualization_factor=365.0` with the comment context of crypto (walk-forward test), suggesting `365` may be the intended crypto alternative.

### 6.2 Does 252 Apply to TOJI?

**[INFERRED — NOT PROVEN]** `252` is the conventional equity trading-days-per-year constant. Crypto markets trade 365 days. Using `252` for crypto understates the true annual periods by approximately `252/365 = 69%`, causing an underestimate of annualized volatility by `sqrt(252/365) ≈ 83%`.

**[PROVEN]** The backtesting tests explicitly recognize this: one test uses `annualization_factor=252.0` (equities) and another uses `365.0` (crypto). This means the TOJI codebase has already internally acknowledged the crypto-vs-equities distinction at the day level.

### 6.3 The 525600 Question

**The CTO has proposed 525600 as the candidate annualization factor for 1-minute crypto data.**

Mathematical derivation: `365 days/year × 24 hours/day × 60 minutes/hour = 525,600 minutes/year`.

**[PROPOSED — NOT PROVEN FROM SOURCE]** If the Feature Platform uses 1-minute bars and TOJI trades crypto 24/7/365, then `sqrt(525600) ≈ 725` is the mathematically correct annualization factor for 1-minute returns.

**Evidence check:**
- Source occurrences of `525600`: **0** [PROVEN]
- Source occurrences of `1440` as annualization: **0** [PROVEN]
- All existing annualization uses daily return granularity: [PROVEN]

**Consequence:** Applying `sqrt(525600)` to 1-minute BTC rolling_std (≈0.001) yields:
```
annualized_vol = 0.001 × 725 = 0.725 (72.5%/year)
```
This is numerically plausible for BTC (actual historical annual vol ≈ 60–100%). However, it requires introducing an entirely new annualization convention that does not exist in the codebase. [PROPOSED]

### 6.4 Annualization Candidates Comparison

| Factor | Formula | Applied to 1-min BTC rolling_std=0.001 | Source support |
|---|---|---|---|
| `252` (daily equities) | `sqrt(252) ≈ 15.87` | `0.001 × 15.87 = 0.016` (1.6%/year — too low) | [PROVEN — but for DAILY returns, not 1-min] |
| `365` (daily crypto) | `sqrt(365) ≈ 19.10` | `0.001 × 19.10 = 0.019` (1.9%/year — too low) | [CONDITIONALLY PROVEN — exists in codebase for daily context] |
| `525600` (1-min crypto) | `sqrt(525600) ≈ 725` | `0.001 × 725 = 0.725` (72.5%/year — plausible for BTC) | [PROPOSED — NOT in source] |
| None (raw per-bar) | `1.0` | `0.001` (0.1% — raw per-bar) | [PROVEN — existing rolling_std output] |

**Critical finding:** If the position-sizing formula is calibrated to `target_volatility = 0.10` as an annualized fraction, and if the input `vol` comes from 1-minute rolling_std, then `sqrt(525600)` is the correct factor. But this is the ONLY context in which `525600` would be appropriate, and it requires:
1. CTO approval of `525600` as the TOJI canonical 1-minute crypto annualization factor
2. Addition of this formula to the Feature Platform transformer
3. Documentation in `.env.example` and governance docs

Neither (2) nor (3) is authorized in FP-3C.

---

## 7. LOOKBACK DECISION

### 7.1 Existing Lookbacks

| Module | Feature | Lookback |
|---|---|---|
| FP transformer `rolling_std` | `std(log_return, 20)` | 20 bars (1-minute) |
| FP transformer `atr` | `mean(TR, 14)` | 14 bars |
| `VolatilityEngine` | `realized_vol` | `window=20` (candle timeframe) |
| Bollinger Bands | `std(close, 20)` | 20 bars |
| `backtesting_engine` | Not windowed — uses full series | Full backtest |

**[PROVEN]** The existing FP convention is a 20-bar rolling window for standard deviation. No other lookback is documented for returns-based volatility in the Feature Platform.

### 7.2 What Lookback Should Canonical Volatility Use?

**[PROPOSED]** The canonical volatility should use a lookback long enough to capture meaningful return dispersion but short enough to remain responsive to regime changes. The repository uses `20` as its standard window, consistent with the Bollinger Band convention and the existing `rolling_std` feature.

However, for annualized volatility calibration, a longer lookback reduces noise. Common industry choices are 20 (1-month daily proxy), 60 (3-month), or 252 (1-year). For 1-minute data:
- 20 bars = 20 minutes (very reactive)
- 60 bars = 1 hour
- 1440 bars = 1 day
- 2880 bars = 2 days

**[UNKNOWN]** The appropriate lookback for a 1-minute annualized volatility feature in TOJI's production context is not established by any source. **This is a CTO decision.**

### 7.3 Recommendation [PROPOSED]

If the CTO approves 1-minute bar annualization with `sqrt(525600)`:
- A minimum lookback of **1440 bars** (1 day equivalent) is recommended for stability, though 20 bars is defensible for intraday responsiveness.
- The warm-up cost increases accordingly.

---

## 8. UNITS

The proposed canonical contract defines:

```
annualized_vol = sample_std(log_returns, N) × sqrt(periods_per_year)
```

**Units:** Dimensionless fraction, annualized basis. Example values:
- `0.10` = 10%/year
- `0.50` = 50%/year
- `0.80` = 80%/year (typical BTC)

**[PROPOSED]** With this definition, `target_volatility = 0.10` means "target 10% annualized portfolio volatility" — consistent with the `VolatilityTargetingEngine` (15%) and `PortfolioRebalancer` (12%) conventions.

**Critical compatibility requirement:** For `vol` and `target_volatility` to be valid inputs to `leverage = target_vol / vol`, both MUST be in the same units (both annualized or both per-period). The proposed contract ensures both are annualized.

---

## 9. WARM-UP

| Window | Lookback | Warm-up bars | Warm-up duration (1-min bars) |
|---|---|---|---|
| 20 bars | 20 | 22 bars (20 + 2 for log_return) | 22 minutes |
| 1440 bars | 1440 | 1442 bars | ~24 hours |
| 2880 bars | 2880 | 2882 bars | ~48 hours |

**[PROPOSED]** During warm-up, the volatility feature returns `NaN` or `0.0` (current FP behavior). This means `PositionSizingOrchestrator` must use the fallback `vol=0.02` during the warm-up period.

**[PROVEN]** The current `fillna(0.0)` behavior in `RollingStdTransformer` produces `0.0` during warm-up. A `0.0` vol in the formula would trigger `max(vol, 0.001) = 0.001`, producing `0.10 / 0.001 = 100×` leverage during warm-up. This is a **warm-up safety risk** that must be addressed in FP-3 implementation.

---

## 10. NaN / ZERO HANDLING

### 10.1 Current Behavior [PROVEN]
- `RollingStdTransformer`: `rolling().std().fillna(0.0)` → returns `0.0` for first 20 bars
- `PositionSizingOrchestrator`: `max(vol, 0.001)` → minimum vol floor of 0.001

### 10.2 Proposed Canonical Behavior [PROPOSED]

| Condition | Proposed Behavior |
|---|---|
| Returns series has < N bars | Return `NaN`; trigger fallback in position sizer |
| Rolling std computes to 0.0 | This is valid (zero-variance period). Do NOT treat as missing. |
| Annualized vol is 0.0 after computation | Apply minimum floor: `max(annualized_vol, min_floor)` |
| NaN from Feature Platform query | Fall back to `vol=0.02` (current behavior) |

### 10.3 Minimum Volatility Floor

**[PROPOSED]** The minimum floor `0.001` in `PositionSizingOrchestrator` prevents division by zero but produces 100× leverage when `target_volatility=0.10`. This floor may need to be recalibrated to the expected `annualized_vol` scale.

If `annualized_vol` for BTC at `sqrt(525600)` scale is typically 0.60–1.00, a floor of `0.001` produces 100× leverage — identical to the raw rolling_std problem.

**[PROPOSED — NOT IMPLEMENTED]** The floor should be calibrated to `target_volatility / max_acceptable_leverage`. For 2× max leverage: `floor = 0.10 / 2.0 = 0.05`.

---

## 11. MISSING / STALE DATA BEHAVIOR

**[PROVEN]** `FeatureStore.query_latest()` returns the most recently stored row. There is no staleness check or TTL in the current implementation. If no tick has fired for a symbol, the Feature Platform may return data that is hours old.

**[PROPOSED — NOT IMPLEMENTED]** The canonical contract should specify a maximum staleness threshold (e.g., `max_age_seconds = 300`). If the stored `annualized_vol` is older than this threshold, the position sizer should use the fallback.

**[UNKNOWN]** How staleness should be detected and reported is not established by any source. This is a future FP-3 implementation decision.

---

## 12. FALLBACK SEMANTICS

### 12.1 Current Fallback [PROVEN]

From `position_sizing/orchestrator.py` L116–117:
```python
# Check FeatureStore for volatility if available, else default to 0.02 (2% daily)
vol = 0.02
```

The comment explicitly labels `0.02` as "2% daily". This is per-day volatility, not per-bar and not annualized.

### 12.2 If Canonical Volatility is Annualized — What Must the Fallback Become?

**[CRITICAL ANALYSIS]** If the canonical feature `annualized_vol` is in annualized units (e.g., 0.60–1.00 for BTC), the fallback `vol = 0.02` (2% annualized) would produce:
```
leverage = 0.10 / 0.02 = 5×
```

But 2% annualized volatility is extremely low — almost no asset has 2%/year vol. This fallback would be semantically wrong at the annualized scale, producing 5× leverage even though the intent was to use a "safe conservative default".

**[PROPOSED]** If canonical vol is annualized at the `sqrt(525600)` scale, the fallback should represent a conservative estimate of typical BTC volatility:
- BTC typical annualized vol at 1-minute scale ≈ 60–100%
- A conservative fallback might be `vol = 0.50` (50%/year), producing:
  ```
  leverage = 0.10 / 0.50 = 0.2× (20% of equity)
  ```
  A very conservative position — appropriate as a fallback.

**[UNKNOWN]** What the new fallback value should be requires CTO decision. Changing it is a production code change blocked until FP-3 is authorized.

### 12.3 Fallback in Dual-Convention Context [PROPOSED]

Alternatively, if the feature pipeline uses a separate internal representation and the position sizer normalizes before comparing to `target_volatility`, the fallback could remain `0.02` provided it represents the same internal unit. But this requires an explicit internal convention decision.

---

## 13. TARGET VOLATILITY SEMANTICS

### 13.1 What Does `target_volatility = 0.10` Mean?

**[PROVEN]** `target_volatility = 0.10` is a `float` in `SizingConfig` with no docstring, no unit annotation, and no description beyond the field name. It is loaded from `os.getenv("TARGET_VOLATILITY", "0.10")`. The env var is not documented in `.env.example`.

**[PROVEN]** The only in-code use is `target_capital = equity × (target_volatility / max(vol, 0.001))` — a ratio with no unit conversion.

**[PROVEN]** The existing test seeds `vol=0.05` and comments `"Leverage scale = 0.10 / 0.05 = 2.0x"`. The test makes no statement about the unit of `vol=0.05`.

**[INFERRED — NOT PROVEN]** Comparison to parallel modules:
- `VolatilityTargetingEngine.target_volatility = 0.15` with test values `realized_volatility = 0.18`, `0.30` → annualized scale
- `PortfolioRebalancer.target_volatility = 0.12` with `portfolio_volatility` passed externally → also appears annualized in usage

**[INFERRED]** `target_volatility = 0.10` is most likely intended as 10% annualized volatility target, consistent with the pattern in the other two components. If this inference is correct, `vol` (the asset volatility input) must also be in annualized units.

**[UNKNOWN]** This cannot be proven without explicit documentation. It requires CTO confirmation.

### 13.2 What Would 0.10 Mean at Different Scales?

| Interpretation | `vol` units | `vol` for BTC | `leverage = 0.10 / vol` | Assessment |
|---|---|---|---|---|
| 10% annualized | Ann. fraction | 0.60–1.00 | 0.10–0.17× (under-leveraged) | Low risk, but likely too conservative |
| 10% of `normalized_atr` scale | Dimensionless ATR ratio | 0.005–0.025 | 4×–20× | Accepted in FP-3B as Decision B |
| 10% per-day | Daily fraction | 0.01–0.05 | 2×–10× | Matches fallback "2% daily" at 5× |
| 10% per-bar (1-min) | Per-1-min fraction | 0.001–0.005 | 20×–100× | Dangerous — same as rolling_std raw |

**At true annualized scale (0.60–1.00 for BTC), `target_volatility=0.10` would produce only 10–17% of equity per position — significantly under-leveraged for an active crypto trading strategy.** This suggests either:
- (a) `target_volatility = 0.10` is NOT at true annualized 1-minute scale → CTO may need to raise it (e.g., to `0.80` for 80% target)
- (b) The formula is intentionally conservative, and a 10–17% position sizing is the design intent
- (c) The convention is NOT annualized at 1-minute granularity but at a different timeframe

**This is the core semantic ambiguity that must be resolved before implementation.** [UNKNOWN — CTO DECISION REQUIRED]

---

## 14. POSITION-SIZING RELATIONSHIP

### 14.1 Exact Formula [PROVEN]

```python
vol_safe = max(vol, 0.001)
target_capital = equity × (target_volatility / vol_safe)
raw_qty = target_capital / price
```

### 14.2 Unit Requirements

For the formula to produce a meaningful result, both `target_volatility` and `vol` must be in identical units. The following table shows what happens at different unit choices:

| `target_volatility` | `vol` (canonical annualized) | leverage | Assessment |
|---|---|---|---|
| 0.10 (10% ann.) | 0.80 (80% ann. BTC) | 0.125× (12.5% of equity) | Very conservative |
| 0.10 | 0.60 (60% ann. BTC) | 0.167× (16.7% of equity) | Very conservative |
| 0.10 | 0.10 (10% ann. target matched) | 1.0× (100% of equity) | Full equity deployment |
| 0.10 | 0.05 (5% ann.) | 2.0× (200% equity) | Test case — currently used |
| 0.80 (80% target) | 0.80 (80% ann. BTC) | 1.0× | Calibrated for BTC |
| 0.80 (80% target) | 0.60 (low vol) | 1.33× | Moderate over-deployment |

**[INFERRED]** If the canonical vol is truly annualized at ~80% for BTC, `target_volatility = 0.10` is miscalibrated by approximately 8×. The CTO would need to set `target_volatility ≈ 0.80` to achieve 1× leverage, or recalibrate the intended leverage scale.

---

## 15. LEVERAGE SAFETY ANALYSIS

### 15.1 Representative Scenarios

Using `target_volatility = 0.10` and the proposed `annualized_vol = rolling_std × sqrt(525600)`:

| Market Condition | rolling_std (1-min) | annualized_vol | leverage = 0.10 / ann_vol | Assessment |
|---|---|---|---|---|
| Very calm BTC | 0.0003 | 0.218 (21.8%) | 0.46× | Under-leveraged |
| Typical BTC | 0.0011 | 0.797 (79.7%) | 0.13× | Very conservative |
| High volatility BTC | 0.0030 | 2.175 (217%) | 0.046× | Near-zero position |
| Low vol flat market | 0.0001 | 0.073 (7.3%) | 1.37× | Moderate |

**Critical observation:** With true annualized volatility at 1-minute scale, `target_volatility = 0.10` would produce **sub-1× leverage in almost all BTC market conditions**. The formula would effectively deploy 5–46% of equity per position. This is conservative but may not match the system's intent for an active trading strategy.

### 15.2 Scenarios with `target_volatility = 0.80`

| Market Condition | annualized_vol | leverage = 0.80 / ann_vol |
|---|---|---|
| Very calm BTC (0.22) | 0.218 | 3.67× |
| Typical BTC (0.80) | 0.797 | 1.00× |
| High vol BTC (2.18) | 2.175 | 0.37× |

This calibration is more intuitive: targeting 80% annualized vol against BTC's typical 80% vol produces 1× leverage (full equity, un-leveraged).

### 15.3 Where Should Leverage Cap Live?

**[INFERRED — NOT PROVEN]** The repository evidence shows two existing leverage caps:
- `VolatilityTargetingEngine`: `min(2.0, scale)` — hardcoded at 2×
- `PortfolioRebalancer`: `min(leverage_scale, 1.5)` — hardcoded at 1.5×

**[PROPOSED — NOT IMPLEMENTED]** Options:
- **A. Inside PositionSizingOrchestrator:** Add `scale = min(max_leverage, target_vol / vol_safe)`. Simplest. But mixes sizing and risk policy.
- **B. Inside Risk Engine:** Risk Engine evaluates the sizing result and rejects/caps it. More architecturally clean. Requires Risk Engine to be in the signal path.
- **C. Inside a shared risk policy config:** A `RiskPolicy` class that all sizing methods reference. Most extensible. Requires new abstraction.
- **D. Via exposure caps (current):** The symbol/portfolio exposure caps already limit final deployment. But raw_qty may be reported at extreme leverage in logs.

**[UNKNOWN — CTO DECISION REQUIRED]** No architectural decision exists in the source. This is deferred to FP-3 implementation gate.

### 15.4 Warm-Up Leverage Risk [PROVEN + INFERRED]

During warm-up (N bars before rolling_std stabilizes):
- `annualized_vol` = `NaN` or `0.0` (due to `fillna(0.0)`)
- `max(0.0, 0.001) = 0.001`
- `leverage = 0.10 / 0.001 = 100×` [PROVEN from current floor behavior]

This is a critical safety issue. The minimum floor `0.001` is designed for the current scale where `vol ≈ 0.02`. At annualized scale it is dangerously low. [INFERRED] The floor must be recalibrated or warm-up must trigger fallback.

---

## 16. BACKTESTING ALIGNMENT

### 16.1 Current Backtesting Convention [PROVEN]

```python
# backtesting_engine/analytics/performance_metrics.py L64-67
variance = sum((r - mean_ret) ** 2 for r in daily_returns) / (n - 1)  # sample std
sample_std = math.sqrt(variance)
volatility = sample_std * math.sqrt(ctx.annualization_factor)          # annualized
```

Input: `daily_returns` (periodic equity returns, named "daily").  
Annualization: `sqrt(252)` default or `sqrt(365)` for crypto tests.

### 16.2 Alignment Path [PROPOSED]

For backtesting to share semantics with the canonical live-trading volatility:
1. Backtesting must compute per-1-minute returns (not per-day equity returns) to match the feature.
2. Backtesting must annualize with `sqrt(525600)` not `sqrt(252)`.

OR:

1. The canonical live feature aggregates 1-minute data to daily bars before computing std.
2. Backtesting uses the same daily returns with `sqrt(365)`.

**[UNKNOWN]** Neither path is established. The current backtesting engine uses equity curve daily returns, not OHLCV candle returns. Alignment would require design decisions in both subsystems.

---

## 17. LIVE TRADING ALIGNMENT

**[PROVEN]** Live trading runs on 1-minute ticks. The Feature Platform receives 1-minute OHLCV bars and computes `log_return` and `rolling_std` at 1-minute granularity.

**[PROVEN]** Position sizing is called per signal, not per tick. The `query_realtime(["volatility"], [symbol])` call retrieves the most recently computed feature value.

**[PROPOSED]** For live trading, the canonical flow would be:
```
1-min tick → Feature Platform → compute log_return → compute rolling_std(N)
                                                             ↓
                              annualized_vol = rolling_std × sqrt(525600)
                                                             ↓
                              PositionSizingOrchestrator.query_realtime(["annualized_vol"])
                                                             ↓
                              leverage = target_volatility / annualized_vol
```

---

## 18. PORTFOLIO / RISK ALIGNMENT

### 18.1 Existing Portfolio Conventions

| Module | `target_volatility` | Input scale | Leverage cap |
|---|---|---|---|
| `VolatilityTargetingEngine` | 0.15 (15%) | Annualized (test: 0.18, 0.30) | min(2.0, scale) |
| `PortfolioRebalancer` | 0.12 (12%) | Annualized (test: 0.18, 0.30) | min(1.5, scale) |
| `PositionSizingOrchestrator` | 0.10 (10%) | **UNKNOWN** | **NONE** |

**[INFERRED]** The three systems appear to use a common conceptual framework (target_vol / realized_vol) with annualized inputs, but they are disconnected implementations with inconsistent `target_volatility` values and inconsistent leverage caps.

**[PROPOSED]** Once the canonical contract is defined, all three modules could reference the same `VolatilityPolicy` or shared risk config. This is a significant refactoring task, beyond the scope of FP-3.

---

## 19. PROPOSED CANONICAL CONTRACT

**STATUS: PROPOSED — NOT YET APPROVED BY CTO**

Every field marked with its evidence classification.

| Contract Field | Proposed Value | Status |
|---|---|---|
| **Feature name** | `annualized_vol` (or `realized_vol_annualized`) | [PROPOSED] |
| **Mathematical definition** | `sample_std(log_returns, N) × sqrt(periods_per_year)` | [PROPOSED — based on codebase convention] |
| **Return definition** | `log(close[t] / close[t-1])` — log returns | [PROVEN — matches `LogReturnTransformer` in FP] |
| **Std formula** | `sample_std (ddof=1)` — matches `analytics/statistics/calculator.py` L47 | [PROVEN as codebase convention; [PROPOSED for FP feature] |
| **Lookback N** | **UNKNOWN** — 20 bars (existing convention) or 1440 bars (1-day stable) | [UNKNOWN — CTO DECISION REQUIRED] |
| **Annualization factor** | `525600` (365×24×60 for crypto 1-minute) | [PROPOSED — NOT in source] |
| **Timeframe** | 1-minute bars | [PROVEN — FP resolution] |
| **Units** | Dimensionless annualized fraction | [PROPOSED] |
| **Annualized?** | YES | [PROPOSED] |
| **Warm-up** | `N + 1` bars (for log_return shift + rolling window) | [PROPOSED] |
| **NaN handling** | Return `NaN`; position sizer uses fallback | [PROPOSED] |
| **Zero handling** | `rolling_std = 0.0` is valid; do NOT fillna(0.0) before annualization — it suppresses valid zero-variance periods | [PROPOSED] |
| **Valid range** | 0.05–5.0 (5% to 500% annualized) for realistic crypto | [PROPOSED] |
| **Minimum floor (in position sizer)** | `target_volatility / max_leverage` e.g. `0.10/2.0 = 0.05` | [PROPOSED — NOT IMPLEMENTED] |
| **Fallback** | Reconsidered — if annualized at 525600 scale, `0.02` is not a safe fallback (see Section 12) | [PROPOSED: recalibrate to 0.50] |
| **Fallback meaning** | Conservative estimate of typical asset annual vol | [PROPOSED] |
| **Target volatility** | Must be recalibrated to annualized scale. `0.10` = 10% — too low for typical BTC at 80%. Consider `0.80`. | [PROPOSED — NOT IMPLEMENTED] |
| **Leverage semantics** | `leverage = target_volatility / annualized_vol` | [PROPOSED] |
| **Leverage cap** | Formula-level cap required: `min(max_leverage, scale)` — consistent with `VolatilityTargetingEngine` and `PortfolioRebalancer` | [PROPOSED — NOT IMPLEMENTED] |
| **Max leverage** | **UNKNOWN** — CTO must define | [UNKNOWN] |
| **Consumer query key** | `query_realtime(["annualized_vol"], [symbol])` — new feature name, not "volatility" | [PROPOSED] |
| **Dependency graph** | `close` → `log_return` → `rolling_std` → `annualized_vol` | [PROPOSED] |
| **Transformer** | New `AnnualizedVolTransformer(rolling_std_col, periods_per_year=525600)` | [PROPOSED — NOT IMPLEMENTED] |
| **Backtesting use** | Backtesting must use same `periods_per_year=525600` when computing 1-minute returns — requires architecture decision | [PROPOSED — NOT IMPLEMENTED] |
| **Testing requirements** | Numeric test: `rolling_std=0.001` → `annualized_vol = 0.001 × 725 ≈ 0.725`; leverage test with known vol inputs | [PROPOSED] |

---

## 20. PROVEN FACTS

All items below are directly verifiable from source code with zero inference.

1. The codebase uses `sample_std (ddof=1) × sqrt(annualization_factor)` as the universal volatility annualization formula across ≥15 source locations. [Source: `analytics/statistics/calculator.py`, `backtesting_engine/analytics/performance_metrics.py`, `research_platform/portfolio_intelligence/metrics.py`, and others]

2. The default `annualization_factor` is `252.0` in all backtesting and analytics modules. The value `525600` appears in **zero** source locations. [Source: `AnalyticsContext.annualization_factor = 252.0`]

3. The existing `rolling_std` FP feature uses pandas `rolling().std()` (ddof=1 by default) on `log_return` with `window=20`. It is NOT annualized — there is no multiplication by any sqrt factor. [Source: `feature_platform/transformers.py` L32–41]

4. The `VolatilityEngine.realized_vol` uses population std (ddof=0): `sqrt(sum((r-mean)^2)/len(returns))`. The FP `RollingStdTransformer` uses sample std (ddof=1). These produce different results. [Source: `market_intelligence/core/analysis/volatility.py` L88]

5. The `VolatilityTargetingEngine` uses `target_volatility / realized_volatility` with `min(2.0, scale)` cap. `realized_volatility` test values are 0.18 and 0.30 — annualized scale. [Source: `portfolio_construction/volatility_targeting.py`; test in `confluence/tests/test_sprint6.py`]

6. The `PortfolioRebalancer` uses `target_volatility / portfolio_volatility` with `min(leverage_scale, 1.5)` cap. Test values: `realized_volatility=0.18`, `0.30`. [Source: `portfolio_intelligence/rebalancer.py`; `confluence/tests/test_sprint6.py`]

7. `PositionSizingOrchestrator` has no formula-level leverage cap. Only downstream exposure caps exist. [Source: `position_sizing/orchestrator.py` L161–199]

8. `TARGET_VOLATILITY` env var is not documented in `.env.example`. Neither is `POSITION_SIZING_METHOD`. [Source: `.env.example` L1–52]

9. The test `test_position_sizing_volatility` seeds `vol=0.05`, uses `target_volatility=0.10`, and seeds the value directly into FeatureStore under the key `"volatility"` (not `"normalized_atr"`, not `"rolling_std"`). [Source: `tests/test_position_sizing.py` L97–121]

10. TOJI trades 24/7 crypto on Binance with 1-minute bars. The trading symbols include `BTCUSDT`, `ETHUSDT`. Crypto markets do not close for weekends or holidays. [Source: `.env.example` L51]

11. `backtesting_engine/tests` uses both `annualization_factor=252.0` (equities) and `annualization_factor=365.0` (crypto daily). Neither uses 525600. [Source: `test_portfolio_analytics.py` L353, L362; `test_walk_forward_validation.py` L403]

---

## 21. INFERENCES

Items below are reasonable conclusions from the evidence but not directly provable from source.

1. [INFERRED] `target_volatility = 0.10` is most likely intended as 10% annualized volatility, consistent with the pattern in `VolatilityTargetingEngine` (15%) and `PortfolioRebalancer` (12%) which use annualized inputs.

2. [INFERRED] The fallback comment "2% daily" means 2% per trading day. At annualized scale with `sqrt(252)`, this would be `0.02 × sqrt(252) ≈ 0.317` (31.7%/year). With `sqrt(365)`: `0.02 × sqrt(365) ≈ 0.382` (38.2%/year). Neither is a natural benchmark for BTC.

3. [INFERRED] The 1-minute Feature Platform was designed before the position-sizing annualization requirements were fully specified. The mismatch between 1-minute bar resolution and `annualization_factor=252` (daily convention) is an architectural gap, not a deliberate design choice.

4. [INFERRED] The `analytics` package (`analytics/statistics/calculator.py`) with `periods_per_year=252` was designed for equity portfolios and imported into TOJI without adapting to crypto 24/7 conventions.

5. [INFERRED] The position-sizing test using `vol=0.05` was written assuming a reasonable leverage of 2× without specifying the unit, suggesting the author was thinking in approximate terms rather than formally defined units.

---

## 22. UNKNOWNS

| # | Unknown | CTO Decision Required? |
|---|---|---|
| **U-1** | Is `target_volatility = 0.10` intended as 10% annualized volatility, 10% daily, or a leverage numerator at normalized_atr scale? | **YES** |
| **U-2** | What is the correct annualization factor for TOJI: 252, 365, 525600, or something else? | **YES** |
| **U-3** | What lookback N should the canonical volatility use: 20, 1440, or other? | **YES** |
| **U-4** | If the annualized vol for BTC is ~0.60–1.00, must `target_volatility` be recalibrated (e.g., to 0.80)? | **YES** |
| **U-5** | What should the new fallback value be at annualized scale? | **YES** |
| **U-6** | What is the maximum acceptable raw formula leverage? Where should the cap live? | **YES** |
| **U-7** | How should backtesting align with the live 1-minute annualization convention? | NO (deferred) |
| **U-8** | Should `annualized_vol` be its own named Feature Platform feature, or aliased as `"volatility"` for backward compatibility? | YES |
| **U-9** | What is the maximum lookback before data freshness becomes a concern? | NO (deferred) |
| **U-10** | Should the minimum vol floor in `PositionSizingOrchestrator` be recalibrated? | **YES** |

---

## 23. RISKS

| Risk | Severity | Description |
|---|---|---|
| **Annualization factor ambiguity** | CRITICAL | Using `sqrt(252)` on 1-minute returns understates annualized vol by 725/15.87 ≈ 46×. Formula would produce deeply wrong leverage. |
| **target_volatility miscalibration** | HIGH | If annualized vol for BTC is ~0.80 and `target_volatility=0.10`, position sizes are ~8× too small vs. design intent. |
| **Warm-up floor danger** | HIGH | `max(vol, 0.001)` produces 100× leverage during warm-up at the annualized scale. |
| **Fallback unit mismatch** | HIGH | `vol=0.02` fallback is in "2% daily" units. If canonical vol is annualized, fallback must be recalibrated. |
| **Convention fragmentation** | MEDIUM | Three systems (PositionSizing/VolatilityTargeting/PortfolioRebalancer) use different `target_volatility` values without a shared specification. |
| **Pop vs sample std** | LOW-MEDIUM | `VolatilityEngine` uses population std; analytics use sample std. Final choice matters for small windows. |
| **Lookback too short** | MEDIUM | A 20-bar (20-minute) rolling std for annualized vol is extremely reactive and noisy. Would require 1440+ bars for daily stability. |
| **No backtesting alignment** | MEDIUM | If live trading uses 525600 annualization and backtesting uses 252, Sharpe/vol metrics from backtest are not comparable to live. |

---

## 24. EXPLICIT NON-GOALS

The following are explicitly OUT OF SCOPE for FP-3C:

1. Any implementation of `AnnualizedVolTransformer`
2. Any registration of a new Feature Platform feature
3. Any change to `PositionSizingOrchestrator`
4. Any change to `rolling_std` transformer parameters
5. Any change to `target_volatility = 0.10` default
6. Any change to `vol = 0.02` fallback
7. Any leverage cap implementation
8. Any backtesting engine changes
9. Any `.env.example` updates
10. Starting FP-4

---

## 25. CTO DECISIONS REQUIRED

The following must be explicitly resolved before FP-3 implementation is authorized:

### Decision 1 (BLOCKING): Annualization Factor
Choose one:
- **D1-A:** `sqrt(252)` — accept existing convention, even though technically wrong for 1-minute crypto (will understate vol significantly; must recalibrate `target_volatility` accordingly)
- **D1-B:** `sqrt(365)` — daily crypto convention (still wrong for 1-minute bars; same issue)
- **D1-C:** `sqrt(525600)` — mathematically correct for 1-minute crypto 24/7. Introduces new convention not yet in codebase. Recommended.
- **D1-D:** `sqrt(1440 × 365)` — equivalent to D1-C but framed as daily_periods × days/year. Same result.

### Decision 2 (BLOCKING): `target_volatility` Recalibration
Choose one:
- **D2-A:** Keep `target_volatility = 0.10`. Accept that this means "target 10% annualized vol". At BTC's 80% typical vol, this produces ~0.125× leverage (12.5% equity per position). Document this explicitly.
- **D2-B:** Recalibrate `target_volatility` to match BTC's typical annualized vol. E.g., set `TARGET_VOLATILITY = 0.80` for approximately 1× leverage at typical BTC vol. This is a configuration change only — no code change.
- **D2-C:** Redefine `target_volatility` as "leverage numerator adjusted for the vol scale". Requires explicit documentation of what scale `vol` is expected at.

### Decision 3 (BLOCKING): Fallback Value
Choose one:
- **D3-A:** Keep `vol = 0.02`. Accept mismatch with annualized scale (this would produce 5× leverage in fallback mode when it should be ~0.125× for D2-A). Document the inconsistency.
- **D3-B:** Change fallback to represent conservative annualized BTC vol (e.g., `vol = 0.50` for 50% annualized). Requires production code change — only authorized in FP-3.
- **D3-C:** Remove the hardcoded fallback and require Feature Platform availability. Return 0 qty if vol is unavailable. Requires production code change.

### Decision 4 (BLOCKING): Lookback N
Choose one:
- **D4-A:** `N = 20` bars (20 minutes). Reactive. Existing FP convention. Low warm-up cost.
- **D4-B:** `N = 1440` bars (1 day). More stable. 24-hour warm-up. Recommended for position sizing.
- **D4-C:** `N = 2880` bars (2 days). High stability. 48-hour warm-up.
- **D4-D:** Other value. CTO specifies.

### Decision 5 (BLOCKING): Minimum Vol Floor / Leverage Cap
Choose one:
- **D5-A:** Recalibrate minimum floor in `PositionSizingOrchestrator` to `target_vol / max_leverage` at the chosen scale. Requires production code change — authorized in FP-3.
- **D5-B:** Add formula-level leverage cap `min(max_leverage, scale)` consistent with `VolatilityTargetingEngine`. Requires production code change — authorized in FP-3.
- **D5-C:** Both D5-A and D5-B.
- **D5-D:** Leave as-is. Accept that exposure caps are sufficient.

### Decision 6 (BLOCKING): Feature Name
Choose one:
- **D6-A:** Register as `"annualized_vol"`. Clean, unambiguous. Requires position sizer to query `"annualized_vol"` instead of `"volatility"`.
- **D6-B:** Register as `"volatility"`. Backward compatible — position sizer already queries this key. But name is ambiguous without documentation.
- **D6-C:** Register as `"realized_vol_annualized"`. Most descriptive. Longer name.

---

## 26. FINAL GATE CLASSIFICATION

```text
╔════════════════════════════════════════════════════════════════════════════════╗
║                                                                                ║
║   SPRINT-004 FP-3C CANONICAL VOLATILITY CONTRACT GATE:                         ║
║                                                                                ║
║   CONDITIONAL — CTO DECISION REQUIRED                                          ║
║                                                                                ║
║   REASON:                                                                      ║
║   The mathematical contract for canonical annualized volatility is fully       ║
║   specified in this document. The formula is established:                      ║
║                                                                                ║
║     annualized_vol = sample_std(log_returns, N) × sqrt(periods_per_year)      ║
║                                                                                ║
║   This formula is internally consistent with the TOJI codebase convention.    ║
║   However, six CTO decisions are required before implementation:               ║
║                                                                                ║
║   DECISION 1: Annualization factor (252 / 365 / 525600 / other)               ║
║   DECISION 2: target_volatility recalibration (keep 0.10 or adjust)           ║
║   DECISION 3: Fallback value (keep 0.02 or recalibrate)                       ║
║   DECISION 4: Lookback N (20 / 1440 / 2880 / other)                           ║
║   DECISION 5: Leverage cap (where and what)                                    ║
║   DECISION 6: Feature name (annualized_vol / volatility / other)              ║
║                                                                                ║
║   RECOMMENDATION:                                                              ║
║   D1-C: sqrt(525600) — mathematically correct for 1-min crypto                ║
║   D2-B: Recalibrate target_volatility to 0.80 for 1× at typical BTC vol       ║
║   D3-B: Recalibrate fallback to 0.50 (50% annualized conservative)            ║
║   D4-B: N=1440 (1 day of 1-minute bars) for stability                         ║
║   D5-B: Add leverage cap min(2.0, scale) in PositionSizingOrchestrator        ║
║   D6-A: Register as "annualized_vol"                                           ║
║                                                                                ║
║   MINIMUM FP-3 IMPLEMENTATION SCOPE (once CTO approves decisions above):      ║
║     1. New transformer: AnnualizedVolTransformer(rolling_std_col, N, factor)  ║
║     2. New FeatureRecord: "annualized_vol" in DEFAULT_FEATURE_DEFINITIONS     ║
║     3. Update query key in PositionSizingOrchestrator: "annualized_vol"       ║
║     4. Recalibrate fallback vol and target_volatility defaults                ║
║     5. Add formula-level leverage cap                                          ║
║     6. Write FP-3 unit tests for the new feature                              ║
║                                                                                ║
║   Production Files Modified (FP-3C): 0                                        ║
║   Test Files Modified (FP-3C): 0                                              ║
║   Configuration Modified (FP-3C): 0                                           ║
║   Environment Modified (FP-3C): 0                                             ║
║                                                                                ║
║   STOP. Awaiting CTO decisions 1–6 from Section 25.                           ║
║                                                                                ║
╚════════════════════════════════════════════════════════════════════════════════╝
```

---

**STOP.** FP-3C canonical contract gate is complete. CTO review required. Do NOT proceed to FP-3D or FP-3 implementation.
