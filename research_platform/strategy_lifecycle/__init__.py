"""TOJI Institutional Strategy Lifecycle Subsystem (R34).

Controls the migration pathways of strategy states (Draft, Backtest, Paper, Production),
enforcing threshold checks (Sharpe ratios, trades count), review approval gates,
audit logging, and deployment rollbacks.
"""
