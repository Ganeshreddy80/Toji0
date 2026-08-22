"""Concrete feature calculators implementing standard financial indicators."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data.feature_store.interfaces import IFeatureDefinition


class EMAFeature(IFeatureDefinition):
    """Exponential Moving Average (EMA) feature."""

    def __init__(self, period: int = 14, version: str = "1.0.0") -> None:
        self._period = period
        self._version = version

    @property
    def name(self) -> str:
        return "EMA"

    @property
    def version(self) -> str:
        return self._version

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        if "close" in df.columns:
            df["ema"] = df["close"].ewm(span=self._period, adjust=False).mean()
        else:
            df["ema"] = np.nan
        return df


class RSIFeature(IFeatureDefinition):
    """Relative Strength Index (RSI) feature."""

    def __init__(self, period: int = 14, version: str = "1.0.0") -> None:
        self._period = period
        self._version = version

    @property
    def name(self) -> str:
        return "RSI"

    @property
    def version(self) -> str:
        return self._version

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        if "close" in df.columns:
            delta = df["close"].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)

            avg_gain = gain.rolling(window=self._period).mean()
            avg_loss = loss.rolling(window=self._period).mean()

            rs = avg_gain / (avg_loss + 1e-10)
            df["rsi"] = 100 - (100 / (1.0 + rs))
        else:
            df["rsi"] = np.nan
        return df


class ATRFeature(IFeatureDefinition):
    """Average True Range (ATR) feature."""

    def __init__(self, period: int = 14, version: str = "1.0.0") -> None:
        self._period = period
        self._version = version

    @property
    def name(self) -> str:
        return "ATR"

    @property
    def version(self) -> str:
        return self._version

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        required = {"high", "low", "close"}
        if required.issubset(df.columns):
            high_low = df["high"] - df["low"]
            high_close = (df["high"] - df["close"].shift(1)).abs()
            low_close = (df["low"] - df["close"].shift(1)).abs()

            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df["atr"] = tr.rolling(window=self._period).mean()
        else:
            df["atr"] = np.nan
        return df


class VWAPFeature(IFeatureDefinition):
    """Volume Weighted Average Price (VWAP) feature."""

    def __init__(self, version: str = "1.0.0") -> None:
        self._version = version

    @property
    def name(self) -> str:
        return "VWAP"

    @property
    def version(self) -> str:
        return self._version

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        required = {"high", "low", "close", "volume"}
        if required.issubset(df.columns):
            typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
            pv = typical_price * df["volume"]
            df["vwap"] = pv.cumsum() / (df["volume"].cumsum() + 1e-10)
        else:
            df["vwap"] = np.nan
        return df


class MACDFeature(IFeatureDefinition):
    """Moving Average Convergence Divergence (MACD) feature."""

    def __init__(
        self, fast: int = 12, slow: int = 26, signal: int = 9, version: str = "1.0.0"
    ) -> None:
        self._fast = fast
        self._slow = slow
        self._signal = signal
        self._version = version

    @property
    def name(self) -> str:
        return "MACD"

    @property
    def version(self) -> str:
        return self._version

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        if "close" in df.columns:
            ema_fast = df["close"].ewm(span=self._fast, adjust=False).mean()
            ema_slow = df["close"].ewm(span=self._slow, adjust=False).mean()
            df["macd"] = ema_fast - ema_slow
            df["macd_signal"] = df["macd"].ewm(span=self._signal, adjust=False).mean()
            df["macd_hist"] = df["macd"] - df["macd_signal"]
        else:
            df["macd"] = np.nan
            df["macd_signal"] = np.nan
            df["macd_hist"] = np.nan
        return df


class ADXFeature(IFeatureDefinition):
    """Average Directional Index (ADX) feature."""

    def __init__(self, period: int = 14, version: str = "1.0.0") -> None:
        self._period = period
        self._version = version

    @property
    def name(self) -> str:
        return "ADX"

    @property
    def version(self) -> str:
        return self._version

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        required = {"high", "low", "close"}
        if required.issubset(df.columns):
            upmove = df["high"].diff()
            downmove = df["low"].diff()

            plus_dm = np.where((upmove > downmove) & (upmove > 0), upmove, 0.0)
            minus_dm = np.where((downmove > upmove) & (downmove > 0), downmove, 0.0)

            high_low = df["high"] - df["low"]
            high_close = (df["high"] - df["close"].shift(1)).abs()
            low_close = (df["low"] - df["close"].shift(1)).abs()
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = tr.rolling(self._period).mean()

            plus_di = 100.0 * (
                pd.Series(plus_dm, index=df.index).rolling(self._period).mean()
                / (atr + 1e-10)
            )
            minus_di = 100.0 * (
                pd.Series(minus_dm, index=df.index).rolling(self._period).mean()
                / (atr + 1e-10)
            )

            dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
            df["adx"] = dx.rolling(self._period).mean()
        else:
            df["adx"] = np.nan
        return df


class MomentumFeature(IFeatureDefinition):
    """Simple Price Momentum feature."""

    def __init__(self, period: int = 10, version: str = "1.0.0") -> None:
        self._period = period
        self._version = version

    @property
    def name(self) -> str:
        return "Momentum"

    @property
    def version(self) -> str:
        return self._version

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        if "close" in df.columns:
            df["momentum"] = df["close"] - df["close"].shift(self._period)
        else:
            df["momentum"] = np.nan
        return df


class VolatilityFeature(IFeatureDefinition):
    """Rolling price returns volatility feature."""

    def __init__(self, period: int = 20, version: str = "1.0.0") -> None:
        self._period = period
        self._version = version

    @property
    def name(self) -> str:
        return "Volatility"

    @property
    def version(self) -> str:
        return self._version

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        if "close" in df.columns:
            df["volatility"] = df["close"].pct_change().rolling(self._period).std()
        else:
            df["volatility"] = np.nan
        return df


class VolumeProfileFeature(IFeatureDefinition):
    """Simplified Volume Profile (POC) feature."""

    def __init__(self, period: int = 24, version: str = "1.0.0") -> None:
        self._period = period
        self._version = version

    @property
    def name(self) -> str:
        return "VolumeProfile"

    @property
    def version(self) -> str:
        return self._version

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        if "close" in df.columns:
            # Point of Control (POC) rolling estimate
            df["volume_profile_poc"] = (
                df["close"]
                .rolling(self._period)
                .apply(
                    lambda x: x.mode().iloc[0] if not x.mode().empty else x.mean(),
                    raw=False,
                )
            )
        else:
            df["volume_profile_poc"] = np.nan
        return df


class FundingFeature(IFeatureDefinition):
    """Funding rate extraction feature."""

    def __init__(self, version: str = "1.0.0") -> None:
        self._version = version

    @property
    def name(self) -> str:
        return "Funding"

    @property
    def version(self) -> str:
        return self._version

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["funding_rate"] = df.get("funding_rate", 0.0)
        return df


class OpenInterestFeature(IFeatureDefinition):
    """Open Interest extraction feature."""

    def __init__(self, version: str = "1.0.0") -> None:
        self._version = version

    @property
    def name(self) -> str:
        return "OpenInterest"

    @property
    def version(self) -> str:
        return self._version

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["open_interest"] = df.get("open_interest", 0.0)
        return df


class LiquidityFeature(IFeatureDefinition):
    """Amihud illiquidity proxy inverse (measure of relative liquidity)."""

    def __init__(self, version: str = "1.0.0") -> None:
        self._version = version

    @property
    def name(self) -> str:
        return "Liquidity"

    @property
    def version(self) -> str:
        return self._version

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        required = {"high", "low", "volume"}
        if required.issubset(df.columns):
            # volume / true range
            range_val = df["high"] - df["low"]
            df["liquidity"] = df["volume"] / (range_val + 1e-10)
        else:
            df["liquidity"] = np.nan
        return df
