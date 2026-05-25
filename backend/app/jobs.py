from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import AgentNetworkReport, AgentORM, AnalyticsMetric, AnalyticsSnapshotORM, TransactionORM


def build_agent_network_report(db: Session) -> AgentNetworkReport:
    transactions = list(db.scalars(select(TransactionORM)).all())
    agents = list(db.scalars(select(AgentORM)).all())
    total_value = sum(tx.amount for tx in transactions)
    volume = len(transactions)
    active_clients = len({tx.customer_phone for tx in transactions})
    total_float = sum(agent.float_balance for agent in agents)
    total_cash = sum(agent.cash_balance for agent in agents)
    float_utilization = round((total_value / max(total_float + total_value, 1)) * 100, 2)
    stockout_rate = round((sum(1 for agent in agents if agent.float_balance < 5_000) / max(len(agents), 1)) * 100, 2)
    return AgentNetworkReport(
        generated_at=datetime.now(UTC),
        metrics=[
            AnalyticsMetric(label="Value", value=total_value, benchmark_delta=-15.2, trend=[12, 18, 16, 25, 19, 31, 24]),
            AnalyticsMetric(label="Volume", value=volume, benchmark_delta=-21.7, trend=[8, 9, 11, 10, 14, 13, 17]),
            AnalyticsMetric(label="Clients", value=active_clients, benchmark_delta=-26.0, trend=[5, 7, 6, 10, 9, 11, 13]),
            AnalyticsMetric(label="Float", value=total_float, benchmark_delta=-16.9, trend=[31, 22, 28, 19, 35, 27, 39]),
            AnalyticsMetric(label="Float Utilization", value=float_utilization, benchmark_delta=3.14, trend=[44, 52, 39, 57, 61, 54, 67]),
            AnalyticsMetric(label="Stockout Rate", value=stockout_rate, benchmark_delta=8.04, trend=[12, 11, 15, 9, 13, 16, 14]),
            AnalyticsMetric(label="Cash Balance", value=total_cash, benchmark_delta=2.32, trend=[21, 23, 25, 20, 28, 31, 27]),
        ],
    )


def materialize_analytics_snapshot(db: Session) -> AnalyticsSnapshotORM:
    report = build_agent_network_report(db)
    snapshot = AnalyticsSnapshotORM(
        id=str(uuid4()),
        snapshot_date=date.today(),
        scope="network",
        metrics=report.model_dump(mode="json"),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot
