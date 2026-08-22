# Strategy Rejection Report

This report outlines the analysis of signal starvation across the 72,202 ticks, detailing the root causes and structural blocker thresholds that prevented trade execution.

---

## Analysis Summary
- **Total analyzed ticks**: 72,202
- **Total signals generated**: 0
- **Total orders executed**: 0

---

## Top Rejection Reasons

### 1. Neutral Technical Indicators (RSI & Breakout)
The Mean Reversion strategy composition logic evaluates indicators like RSI and Breakout status. In the simulated environment, the prices fluctuated narrowly, causing:
- RSI to remain between 30 and 70 (categorized as "RSI neutral").
- Breakout status to remain as "none" (categorized as "No breakout").
These conditions collectively forced the strategy composer to emit a `HOLD` decision on almost 100% of the incoming ticks.

### 2. High AI Signal Confluence Thresholds
The `AISignalGenerator` requires a confluence score of `score >= 70.0` to trigger a BUY signal, and `score <= 30.0` to trigger a SELL signal. 
- In the absence of multi-timeframe trend alignment (HTF bias was `NEUTRAL` due to lack of swing breaks), order block validation, or active Fair Value Gaps, the confluence score remained at `50.0` (or `60.0`/`40.0` based on VWAP position).
- This score is insufficient to pass the $\ge 70$ or $\le 30$ threshold, leading to 100% `WAIT` signals.

### 3. Missing/Insufficient Historical Volatility Warmup (ATR = 0.0)
At startup, the `PriceActionOrchestrator` requires at least 5 completed 1-minute bars to compute swing fractal points and at least 2 bars to compute ATR.
- When ATR is `0.0`, the Mean Reversion bands collapse to the exact VWAP price ($VWAP \pm 2 \times 0.0$).
- Consequently, any minor tick fluctuation is interpreted as being exactly at the mean, generating a `HOLD` state rather than a breakout or reversion trigger.
