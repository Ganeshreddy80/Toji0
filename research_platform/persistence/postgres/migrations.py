"""SQLAlchemy ORM models definition and database schema migrations.
"""

from __future__ import annotations

import logging
from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime, JSON
from sqlalchemy.engine import Engine

from research_platform.persistence.postgres.base_repository import Base

logger = logging.getLogger(__name__)


# ── OMS Models ────────────────────────────────────────────────────────

class OrderModel(Base):
    __tablename__ = "orders"
    order_id = Column(String, primary_key=True)
    strategy_id = Column(String)
    symbol = Column(String)
    side = Column(String)
    quantity = Column(Float)
    price = Column(Float)
    order_type = Column(String)
    status = Column(String)


class TradeModel(Base):
    __tablename__ = "trades"
    trade_id = Column(String, primary_key=True)
    order_id = Column(String)
    symbol = Column(String)
    side = Column(String)
    quantity = Column(Float)
    price = Column(Float)
    timestamp = Column(DateTime)


class PositionModel(Base):
    __tablename__ = "positions"
    position_id = Column(String, primary_key=True)
    symbol = Column(String)
    quantity = Column(Float)
    average_price = Column(Float)


class TradeJournalModel(Base):
    __tablename__ = "trade_journals"
    journal_id = Column(String, primary_key=True)
    order_id = Column(String)
    strategy_id = Column(String)
    symbol = Column(String)
    pnl = Column(Float)
    tags = Column(JSON)
    data = Column(JSON)


class DailyJournalModel(Base):
    __tablename__ = "daily_journals"
    date = Column(String, primary_key=True)
    data = Column(JSON)


class TradeStatisticsModel(Base):
    __tablename__ = "trade_statistics"
    stats_id = Column(String, primary_key=True)
    data = Column(JSON)


# ── Portfolio & Analytics Models ──────────────────────────────────────

class PortfolioModel(Base):
    __tablename__ = "portfolios"
    portfolio_id = Column(String, primary_key=True)
    weights = Column(JSON)
    last_rebalanced = Column(DateTime)


class AnalyticsModel(Base):
    __tablename__ = "analytics"
    analytics_id = Column(String, primary_key=True)
    metric_name = Column(String)
    metric_value = Column(Float)
    timestamp = Column(DateTime)


# ── Strategy & Research Models ────────────────────────────────────────

class StrategyModel(Base):
    __tablename__ = "strategies"
    strategy_id = Column(String, primary_key=True)
    name = Column(String)
    status = Column(String)
    config = Column(JSON)


class ExperimentModel(Base):
    __tablename__ = "experiments"
    experiment_id = Column(String, primary_key=True)
    name = Column(String)
    status = Column(String)
    metrics = Column(JSON)


# ── Monitoring Models ─────────────────────────────────────────────────

class MonitoringStatusModel(Base):
    __tablename__ = "monitoring_status"
    service_name = Column(String, primary_key=True)
    response_time_ms = Column(Float)
    is_alive = Column(Boolean)
    last_check = Column(DateTime)


class MonitoringAlertModel(Base):
    __tablename__ = "monitoring_alerts"
    alert_id = Column(String, primary_key=True)
    level = Column(String)
    source = Column(String)
    message = Column(String)
    timestamp = Column(DateTime)


class MonitoringMetricModel(Base):
    __tablename__ = "monitoring_metrics"
    metric_name = Column(String, primary_key=True)
    value = Column(Integer)


# ── Reporting Models ──────────────────────────────────────────────────

class ReportModel(Base):
    __tablename__ = "reports"
    report_id = Column(String, primary_key=True)
    title = Column(String)
    content = Column(String)
    format_type = Column(String)
    created_at = Column(DateTime)


# ── Configuration & Scheduler Models ──────────────────────────────────

class ConfigurationModel(Base):
    __tablename__ = "configurations"
    key = Column(String, primary_key=True)
    value = Column(JSON)


class JobModel(Base):
    __tablename__ = "jobs"
    job_id = Column(String, primary_key=True)
    name = Column(String)
    task_type = Column(String)
    schedule_expr = Column(String)
    priority = Column(Integer)
    status = Column(String)


class TradeLedgerModel(Base):
    __tablename__ = "trade_ledger"
    trade_id = Column(String, primary_key=True)
    order_id = Column(String)
    symbol = Column(String)
    side = Column(String)
    quantity = Column(Float)
    entry_price = Column(Float)
    exit_price = Column(Float)
    commission = Column(Float)
    slippage = Column(Float)
    realized_pnl = Column(Float)
    timestamp = Column(DateTime)


# ── Migrations Engine ─────────────────────────────────────────────────

def run_migrations(engine: Engine) -> None:
    """Creates all defined tables if they do not exist."""
    logger.info("Running automatic database migrations...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema synchronized successfully.")
    except Exception as e:
        logger.warning("Database schema synchronization warning/concurrent run: %s", e)
