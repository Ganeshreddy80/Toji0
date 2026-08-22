"""Risk Governance Telegram alert formatters."""

from __future__ import annotations


def format_risk_alert(
    problem: str,
    action: str,
    portfolio_usdt: float,
    status: str = "SAFE MODE",
    mode: str = "HALTED",
) -> str:
    """Format a critical risk alert for Telegram."""
    return (
        f"🚨 TOJI RISK ALERT\n\n"
        f"Problem:\n"
        f"{problem}\n\n"
        f"Action:\n"
        f"{action}\n\n"
        f"Portfolio:\n"
        f"{portfolio_usdt:,.0f} USDT\n\n"
        f"Status:\n"
        f"{status}\n\n"
        f"Mode:\n"
        f"{mode}"
    )


def format_risk_online_alert(
    mode: str = "NORMAL",
    protection: str = "ACTIVE",
    kill_switch: str = "READY",
) -> str:
    """Format the system-boot risk governance online message."""
    return (
        f"🛡 TOJI RISK SYSTEM ONLINE\n\n"
        f"Mode:\n"
        f"{mode}\n\n"
        f"Protection:\n"
        f"{protection}\n\n"
        f"Kill Switch:\n"
        f"{kill_switch}"
    )


def format_anomaly_alert(
    anomaly_type: str,
    symbol: str,
    detail: str,
    action: str = "Trading paused",
) -> str:
    """Format a market anomaly detection alert."""
    return (
        f"⚠️ MARKET ANOMALY DETECTED\n\n"
        f"Type:\n"
        f"{anomaly_type}\n\n"
        f"Symbol:\n"
        f"{symbol}\n\n"
        f"Detail:\n"
        f"{detail}\n\n"
        f"Action:\n"
        f"{action}"
    )


def format_audit_rejection_alert(
    signal: str,
    symbol: str,
    reason: str,
) -> str:
    """Format an AI signal rejection alert."""
    return (
        f"🔒 AI SIGNAL REJECTED\n\n"
        f"Signal:\n"
        f"{signal}\n\n"
        f"Symbol:\n"
        f"{symbol}\n\n"
        f"Reason:\n"
        f"{reason}"
    )
