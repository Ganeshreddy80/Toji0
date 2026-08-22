"""Mathematical transformers and indicator functions for pipeline calculations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Any


class CloseTransformer:
    """Returns raw price close series."""
    def transform(self, df: pd.DataFrame) -> pd.Series:
        if "close" not in df.columns:
            raise KeyError("DataFrame must contain a 'close' column.")
        return df["close"]


class LogReturnTransformer:
    """Calculates log returns of price series."""
    def __init__(self, target_column: str = "close") -> None:
        self.target = target_column

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if self.target not in df.columns:
            raise KeyError(f"DataFrame must contain column '{self.target}'.")
        prices = df[self.target]
        log_ret = np.log(prices / prices.shift(1))
        return log_ret.fillna(0.0)


class RollingStdTransformer:
    """Calculates rolling standard deviation of input series."""
    def __init__(self, target_column: str, window: int = 20) -> None:
        self.target = target_column
        self.window = window

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if self.target not in df.columns:
            raise KeyError(f"DataFrame must contain column '{self.target}'.")
        return df[self.target].rolling(window=self.window).std().fillna(0.0)


class AnnualizedVolTransformer:
    """Canonical annualized realized volatility for position sizing.

    Formula:
        annualized_vol = sample_std(log_returns, N) * sqrt(periods_per_year)

    Where:
        - log_returns = log(close[t] / close[t-1])
        - N = lookback window in 1-minute bars (default 1440 = ~1 trading day)
        - periods_per_year = 525600 (365 days * 24 hours * 60 minutes, crypto 24/7)
        - sample_std uses ddof=1 (pandas rolling().std() default)

    IMPORTANT WARM-UP SAFETY:
        During the first N bars, the output is NaN (not 0.0).
        Do NOT fillna(0.0) here. NaN signals the position sizer to use its
        configured fallback_volatility instead of the dangerous 0.001 floor
        that would produce ~100x leverage.

    Units:
        Dimensionless annualized fraction (e.g. 0.725 = 72.5%/year for typical BTC).
    """

    # 365 days * 24 hours * 60 minutes — crypto markets trade 24/7/365
    CRYPTO_PERIODS_PER_YEAR: int = 525600

    def __init__(
        self,
        log_return_column: str = "log_return",
        window: int = 1440,
        periods_per_year: int = CRYPTO_PERIODS_PER_YEAR,
    ) -> None:
        self.log_return_col = log_return_column
        self.window = window
        self.periods_per_year = periods_per_year
        self._annualization_factor = periods_per_year ** 0.5

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if self.log_return_col not in df.columns:
            raise KeyError(
                f"DataFrame must contain column '{self.log_return_col}' for AnnualizedVolTransformer. "
                f"Ensure 'log_return' is computed before 'annualized_vol' in the DAG."
            )
        # rolling().std() uses ddof=1 by default (sample standard deviation)
        # NaN is preserved during warm-up — do NOT fillna here.
        per_bar_std = df[self.log_return_col].rolling(window=self.window).std()
        return per_bar_std * self._annualization_factor


class AtrTransformer:
    """Calculates Average True Range (ATR) from high, low, close price fields."""
    def __init__(self, window: int = 14) -> None:
        self.window = window

    def transform(self, df: pd.DataFrame) -> pd.Series:
        for col in ["high", "low", "close"]:
            if col not in df.columns:
                raise KeyError(f"DataFrame must contain column '{col}' for ATR computation.")
        
        high = df["high"]
        low = df["low"]
        close_prev = df["close"].shift(1)

        tr1 = high - low
        tr2 = (high - close_prev).abs()
        tr3 = (low - close_prev).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.window).mean()
        return atr.fillna(0.0)


class NormalizedAtrTransformer:
    """Normalizes ATR by dividing it by the price close."""
    def __init__(self, atr_column: str, close_column: str = "close") -> None:
        self.atr_col = atr_column
        self.close_col = close_column

    def transform(self, df: pd.DataFrame) -> pd.Series:
        for col in [self.atr_col, self.close_col]:
            if col not in df.columns:
                raise KeyError(f"DataFrame must contain column '{col}' for Normalization.")
        return (df[self.atr_col] / (df[self.close_col] + 1e-10)).fillna(0.0)


class RiskScoreTransformer:
    """Computes a risk score based on volatility z-score."""
    def __init__(self, vol_column: str, window: int = 50) -> None:
        self.vol_col = vol_column
        self.window = window

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if self.vol_col not in df.columns:
            raise KeyError(f"DataFrame must contain column '{self.vol_col}' for RiskScore.")
        
        vols = df[self.vol_col]
        mean = vols.rolling(window=self.window).mean()
        std = vols.rolling(window=self.window).std()
        
        z_score = (vols - mean) / (std + 1e-10)
        return z_score.fillna(0.0)


class SignalTransformer:
    """Generates trigger signals based on risk score thresholds."""
    def __init__(self, risk_column: str, threshold: float = 2.0) -> None:
        self.risk_col = risk_column
        self.threshold = threshold

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if self.risk_col not in df.columns:
            raise KeyError(f"DataFrame must contain column '{self.risk_col}'.")
        # 1.0 for buy/sell trigger, 0.0 otherwise
        return (df[self.risk_col].abs() > self.threshold).astype(float)


class OpenTransformer:
    """Returns raw price open series."""
    def transform(self, df: pd.DataFrame) -> pd.Series:
        if "open" not in df.columns:
            raise KeyError("DataFrame must contain an 'open' column.")
        return df["open"]


class HighTransformer:
    """Returns raw price high series."""
    def transform(self, df: pd.DataFrame) -> pd.Series:
        if "high" not in df.columns:
            raise KeyError("DataFrame must contain a 'high' column.")
        return df["high"]


class LowTransformer:
    """Returns raw price low series."""
    def transform(self, df: pd.DataFrame) -> pd.Series:
        if "low" not in df.columns:
            raise KeyError("DataFrame must contain a 'low' column.")
        return df["low"]


class VolumeTransformer:
    """Returns raw volume series."""
    def transform(self, df: pd.DataFrame) -> pd.Series:
        if "volume" not in df.columns:
            raise KeyError("DataFrame must contain a 'volume' column.")
        return df["volume"]


class EmaTransformer:
    """Calculates Exponential Moving Average (EMA) of close prices."""
    def __init__(self, target_column: str = "close", window: int = 9) -> None:
        self.target = target_column
        self.window = window

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if self.target not in df.columns:
            raise KeyError(f"DataFrame must contain column '{self.target}'.")
        return df[self.target].ewm(span=self.window, adjust=False).mean().fillna(df[self.target])


class RsiTransformer:
    """Calculates Relative Strength Index (RSI) of close prices."""
    def __init__(self, target_column: str = "close", window: int = 14) -> None:
        self.target = target_column
        self.window = window

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if self.target not in df.columns:
            raise KeyError(f"DataFrame must contain column '{self.target}'.")
        delta = df[self.target].diff()
        gain = (delta.where(delta > 0, 0.0)).rolling(window=self.window).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=self.window).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi.fillna(50.0)


class VolumeChangeTransformer:
    """Calculates percentage change of volume."""
    def transform(self, df: pd.DataFrame) -> pd.Series:
        if "volume" not in df.columns:
            raise KeyError("DataFrame must contain a 'volume' column.")
        return df["volume"].pct_change().fillna(0.0)


class SupportTransformer:
    """Calculates support level (rolling minimum of low prices)."""
    def __init__(self, window: int = 20) -> None:
        self.window = window

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if "low" not in df.columns:
            raise KeyError("DataFrame must contain column 'low'.")
        return df["low"].rolling(window=self.window).min().fillna(df["low"])


class ResistanceTransformer:
    """Calculates resistance level (rolling maximum of high prices)."""
    def __init__(self, window: int = 20) -> None:
        self.window = window

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if "high" not in df.columns:
            raise KeyError("DataFrame must contain column 'high'.")
        return df["high"].rolling(window=self.window).max().fillna(df["high"])


class BreakoutTransformer:
    """Detects breakout of price above resistance or below support."""
    def transform(self, df: pd.DataFrame) -> pd.Series:
        if "close" not in df.columns or "resistance" not in df.columns or "support" not in df.columns:
            raise KeyError("DataFrame must contain close, resistance, and support columns.")
        res_prev = df["resistance"].shift(1).fillna(df["resistance"])
        sup_prev = df["support"].shift(1).fillna(df["support"])
        
        breakout = pd.Series("none", index=df.index)
        breakout.loc[df["close"] > res_prev] = "breakout_high"
        breakout.loc[df["close"] < sup_prev] = "breakout_low"
        return breakout


class TrendDirectionTransformer:
    """Calculates trend direction (bullish or bearish) based on ema9/ema21 comparison."""
    def transform(self, df: pd.DataFrame) -> pd.Series:
        if "ema9" not in df.columns or "ema21" not in df.columns:
            raise KeyError("DataFrame must contain ema9 and ema21 columns.")
        
        trend = pd.Series("bullish", index=df.index)
        trend.loc[df["ema9"] < df["ema21"]] = "bearish"
        return trend
