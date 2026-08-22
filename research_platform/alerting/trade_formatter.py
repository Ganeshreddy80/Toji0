"""TOJI Trading Intelligence Alert Formatters.

Formats startup, heartbeat, signals, and trade executions for Telegram monitoring.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def format_startup_alert(
    timestamp: str,
    markets: list[str],
    db_status: str = "CONNECTED",
    redis_status: str = "CONNECTED",
    binance_status: str = "CONNECTED",
    telegram_status: str = "CONNECTED",
    starting_balance: float = 100000.0,
) -> str:
    """Format the system startup message."""
    markets_str = "\n".join(markets)
    return (
        f"🚀 TOJI PAPER ENGINE ONLINE\n\n"
        f"Mode:\n"
        f"PAPER\n\n"
        f"Started:\n"
        f"{timestamp}\n\n"
        f"Active Markets:\n"
        f"{markets_str}\n\n"
        f"Modules:\n"
        f"Market Gateway: ONLINE\n"
        f"Feature Engine: ONLINE\n"
        f"Price Action Engine: ONLINE\n"
        f"Strategy Engine: ONLINE\n"
        f"AI Signal Engine: ONLINE\n"
        f"OMS: ONLINE\n"
        f"Paper Trading: ONLINE\n"
        f"Risk Engine: ONLINE\n"
        f"Safety System: ACTIVE\n\n"
        f"Connections:\n"
        f"PostgreSQL:\n"
        f"{db_status}\n\n"
        f"Redis:\n"
        f"{redis_status}\n\n"
        f"Binance:\n"
        f"{binance_status}\n\n"
        f"Telegram:\n"
        f"{telegram_status}\n\n"
        f"Account:\n"
        f"Mode:\n"
        f"Paper Trading\n\n"
        f"Starting Balance:\n"
        f"{starting_balance} USDT\n\n"
        f"Status:\n"
        f"Waiting for opportunities"
    )


def format_heartbeat_alert(
    uptime: str,
    market_status: str,
    watching: list[str],
    ticks: int,
    signals: int,
    trades: int,
    balance: float,
    pnl: float,
    db_status: str,
    redis_status: str,
    memory: str,
    safety_status: str = "ACTIVE",
) -> str:
    """Format the periodic health heartbeat report."""
    watching_str = "\n".join(watching)
    return (
        f"❤️ TOJI HEALTH REPORT\n\n"
        f"Uptime:\n"
        f"{uptime}\n\n"
        f"Market:\n"
        f"{market_status}\n\n"
        f"Watching:\n"
        f"{watching_str}\n\n"
        f"Ticks Processed:\n"
        f"{ticks}\n\n"
        f"Signals Today:\n"
        f"{signals}\n\n"
        f"Trades Today:\n"
        f"{trades}\n\n"
        f"Portfolio:\n"
        f"Balance:\n"
        f"{balance} USDT\n"
        f"PnL:\n"
        f"{pnl} USDT\n\n"
        f"DB:\n"
        f"{db_status}\n\n"
        f"Redis:\n"
        f"{redis_status}\n\n"
        f"Memory:\n"
        f"{memory}\n\n"
        f"Safety:\n"
        f"{safety_status}"
    )


def format_signal_alert(
    symbol: str,
    decision: str,
    price: float,
    timeframe: str,
    confidence: float,
    reasoning: str,
    trend: str = "bullish",
    breakout: str = "no",
    sr: str = "at support",
    indicators: str = "RSI: 42.5, VWAP: crossing",
    risk: str = "Position size within limits, Risk score: 92/100",
    final_decision: str = "EXECUTE PAPER ORDER",
) -> str:
    """Format a signal detected alert."""
    confidence_str = f"{confidence * 100:.0f}%" if isinstance(confidence, float) and confidence <= 1.0 else str(confidence)
    if "%" not in confidence_str:
         confidence_str = f"{confidence_str}%"
    return (
        f"🧠 TOJI SIGNAL DETECTED\n\n"
        f"Symbol:\n"
        f"{symbol}\n\n"
        f"Decision:\n"
        f"{decision}\n\n"
        f"Current Price:\n"
        f"{price}\n\n"
        f"Timeframe:\n"
        f"{timeframe}\n\n"
        f"Confidence:\n"
        f"{confidence_str}\n\n"
        f"Reason:\n"
        f"{reasoning}\n\n"
        f"Price Action:\n"
        f"- trend: {trend}\n"
        f"- breakout: {breakout}\n"
        f"- support/resistance: {sr}\n\n"
        f"Indicators:\n"
        f"{indicators}\n\n"
        f"Risk:\n"
        f"{risk}\n\n"
        f"Final Decision:\n"
        f"{final_decision}"
    )


def format_trade_alert(
    symbol: str,
    side: str,
    entry: float,
    quantity: float,
    sl: float,
    tp: float,
    risk: str,
    reason: str,
    trade_id: str,
    # Execution quality fields (optional — backward compatible)
    fill_price: float = 0.0,
    slippage_pct: float = 0.0,
    fee_usdt: float = 0.0,
    liquidity_check: str = "PASS",
    execution_score: float = 0.0,
) -> str:
    """Format a trade execution alert with institutional execution detail."""
    expected_str = f"{entry:.2f}" if entry else "N/A"
    filled_str = f"{fill_price:.2f}" if fill_price else expected_str
    slip_str = f"{slippage_pct:.2f}%"
    fee_str = f"{fee_usdt:.2f} USDT"
    score_str = f"{execution_score:.0f}/100" if execution_score else "N/A"

    return (
        f"📈 PAPER TRADE EXECUTED\n\n"
        f"Coin:\n"
        f"{symbol}\n\n"
        f"Signal:\n"
        f"{side}\n\n"
        f"Expected:\n"
        f"{expected_str}\n\n"
        f"Filled:\n"
        f"{filled_str}\n\n"
        f"Slippage:\n"
        f"{slip_str}\n\n"
        f"Fee:\n"
        f"{fee_str}\n\n"
        f"Liquidity:\n"
        f"{liquidity_check}\n\n"
        f"Risk:\n"
        f"{risk}\n\n"
        f"Execution Score:\n"
        f"{score_str}\n\n"
        f"Stop Loss:\n"
        f"{sl:.2f}\n\n"
        f"Target:\n"
        f"{tp:.2f}\n\n"
        f"Reason:\n"
        f"{reason}\n\n"
        f"Trade ID:\n"
        f"{trade_id}"
    )

