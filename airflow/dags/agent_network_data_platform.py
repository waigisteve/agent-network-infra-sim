from __future__ import annotations

import json
from datetime import datetime, timedelta

import urllib.request
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator


API_BASE_URL = "http://api:8000"


def post_json(path: str, payload: dict[str, object], token: str | None = None) -> dict[str, object]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{API_BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def check_api_readiness() -> dict[str, object]:
    with urllib.request.urlopen(f"{API_BASE_URL}/ready", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def admin_token() -> str:
    response = post_json("/api/v1/auth/login", {"email": "admin@example.com", "password": "password"})
    return str(response["access_token"])


def run_key(context: dict[str, object]) -> str:
    return str(context["ts_nodash"]).replace("+", "").replace(":", "")


def ingest_telco_sample(**context: object) -> dict[str, object]:
    token = admin_token()
    key = run_key(context)
    return post_json(
        "/api/v1/integrations/telco-transactions",
        {
            "contract_name": "telco_transactions_v1",
            "source_reference": f"airflow-telco-sample-{key}",
            "records": [
                {
                    "provider_reference": f"airflow-telco-ref-{key}",
                    "agent_id": "agent_neema",
                    "customer_msisdn": "256770000010",
                    "transaction_type": "DEPOSIT",
                    "amount": 3500,
                    "commission": 42,
                    "status": "SUCCESS",
                    "created_at": "2026-05-28T08:00:00+00:00",
                }
            ],
        },
        token,
    )


def ingest_bank_settlement_sample(**context: object) -> dict[str, object]:
    token = admin_token()
    key = run_key(context)
    return post_json(
        "/api/v1/integrations/bank-settlements",
        {
            "contract_name": "bank_settlements_v1",
            "source_reference": f"airflow-bank-settlement-{key}",
            "records": [
                {
                    "settlement_reference": f"airflow-bank-settle-{key}",
                    "settlement_date": "2026-05-28",
                    "transaction_count": 1,
                    "gross_amount": 3500,
                    "commission_amount": 42,
                    "currency": "UGX",
                }
            ],
        },
        token,
    )


def reconcile_sample(**context: object) -> dict[str, object]:
    token = admin_token()
    key = run_key(context)
    return post_json(
        "/api/v1/integrations/reconcile-settlement",
        {"partner_id": "partner_bank_b_ug", "settlement_reference": f"airflow-bank-settle-{key}"},
        token,
    )


default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


with DAG(
    dag_id="agent_network_partner_ingestion",
    default_args=default_args,
    description="Validate partner feeds, load raw data, reconcile settlements, and build dbt marts.",
    schedule_interval="@daily",
    start_date=datetime(2026, 5, 28),
    catchup=False,
    tags=["agent-network", "partner-integrations", "dbt"],
) as dag:
    ready = PythonOperator(task_id="check_api_readiness", python_callable=check_api_readiness)
    telco = PythonOperator(task_id="ingest_telco_transactions", python_callable=ingest_telco_sample)
    bank = PythonOperator(task_id="ingest_bank_settlement", python_callable=ingest_bank_settlement_sample)
    reconcile = PythonOperator(task_id="reconcile_bank_settlement", python_callable=reconcile_sample)
    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command="cd /opt/airflow/dbt && dbt build --profiles-dir profiles",
    )

    ready >> [telco, bank] >> reconcile >> dbt_build
