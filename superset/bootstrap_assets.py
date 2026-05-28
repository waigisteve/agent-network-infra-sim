from __future__ import annotations

import json

from superset import db
from superset.app import create_app

app = create_app()
app.app_context().push()

from superset.connectors.sqla.models import SqlaTable, TableColumn  # noqa: E402
from superset.models.core import Database  # noqa: E402
from superset.models.dashboard import Dashboard  # noqa: E402
from superset.models.slice import Slice  # noqa: E402


DATASETS = [
    ("analytics_marts", "mart_partner_network_health"),
    ("analytics_marts", "mart_liquidity_risk"),
    ("analytics_intermediate", "int_settlement_reconciliation"),
]

DASHBOARDS = [
    {
        "title": "Partner Network Health",
        "slug": "partner-network-health",
        "dataset": ("analytics_marts", "mart_partner_network_health"),
        "charts": [
            ("Partner Network Health Table", "table"),
            ("Partner Transaction Value", "big_number_total"),
        ],
    },
    {
        "title": "Agent Liquidity Risk",
        "slug": "agent-liquidity-risk",
        "dataset": ("analytics_marts", "mart_liquidity_risk"),
        "charts": [
            ("Agent Liquidity Risk Table", "table"),
            ("High Risk Agent Count", "big_number_total"),
        ],
    },
    {
        "title": "Reconciliation Exceptions",
        "slug": "reconciliation-exceptions",
        "dataset": ("analytics_intermediate", "int_settlement_reconciliation"),
        "charts": [
            ("Settlement Reconciliation Table", "table"),
            ("Exception Count", "big_number_total"),
        ],
    },
]


def get_database() -> Database:
    database = db.session.query(Database).filter_by(database_name="agent_network").one_or_none()
    if database is None:
        raise RuntimeError("Superset database connection 'agent_network' does not exist")
    return database


def ensure_dataset(database: Database, schema: str, table_name: str) -> SqlaTable:
    dataset = (
        db.session.query(SqlaTable)
        .filter_by(database_id=database.id, schema=schema, table_name=table_name)
        .one_or_none()
    )
    if dataset is None:
        dataset = SqlaTable(database=database, schema=schema, table_name=table_name)
        db.session.add(dataset)
        db.session.flush()
    dataset.fetch_metadata()
    db.session.flush()
    return dataset


def ensure_chart(title: str, viz_type: str, dataset: SqlaTable) -> Slice:
    chart = db.session.query(Slice).filter_by(slice_name=title).one_or_none()
    params = chart_params(viz_type, dataset)
    if chart is None:
        chart = Slice(
            slice_name=title,
            viz_type=viz_type,
            datasource_id=dataset.id,
            datasource_type="table",
            params=json.dumps(params),
        )
        db.session.add(chart)
    else:
        chart.viz_type = viz_type
        chart.datasource_id = dataset.id
        chart.datasource_type = "table"
        chart.params = json.dumps(params)
    db.session.flush()
    return chart


def chart_params(viz_type: str, dataset: SqlaTable) -> dict[str, object]:
    columns = [column.column_name for column in dataset.columns]
    if viz_type == "big_number_total":
        metric = numeric_metric(dataset) or "COUNT(*)"
        return {"datasource": f"{dataset.id}__table", "viz_type": viz_type, "metric": metric}
    return {
        "datasource": f"{dataset.id}__table",
        "viz_type": "table",
        "all_columns": columns[:8],
        "row_limit": 1000,
    }


def numeric_metric(dataset: SqlaTable) -> str | None:
    for column in dataset.columns:
        if is_numeric(column):
            return f"SUM({column.column_name})"
    return None


def is_numeric(column: TableColumn) -> bool:
    type_text = (column.type or "").lower()
    return any(token in type_text for token in ("int", "numeric", "double", "float", "decimal"))


def ensure_dashboard(title: str, slug: str, charts: list[Slice]) -> Dashboard:
    dashboard = db.session.query(Dashboard).filter_by(slug=slug).one_or_none()
    if dashboard is None:
        dashboard = Dashboard(dashboard_title=title, slug=slug, published=True)
        db.session.add(dashboard)
    dashboard.slices = charts
    dashboard.position_json = json.dumps({})
    db.session.flush()
    return dashboard


def main() -> None:
    database = get_database()
    datasets = {key: ensure_dataset(database, *key) for key in DATASETS}
    for spec in DASHBOARDS:
        dataset = datasets[spec["dataset"]]
        charts = [ensure_chart(title, viz_type, dataset) for title, viz_type in spec["charts"]]
        ensure_dashboard(str(spec["title"]), str(spec["slug"]), charts)
    db.session.commit()
    print("Superset datasets, charts, and dashboards created")


if __name__ == "__main__":
    main()
