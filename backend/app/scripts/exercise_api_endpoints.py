from __future__ import annotations

import argparse
import json
import random
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any


READ_ENDPOINTS = (
    "/api/v1/me",
    "/api/v1/agents",
    "/api/v1/field-agents",
    "/api/v1/customers",
    "/api/v1/float/requests",
    "/api/v1/float/reconciliation",
    "/api/v1/transactions",
    "/api/v1/commissions",
    "/api/v1/reports/agent-network",
    "/api/v1/reports/agent/agent_neema",
    "/api/v1/maps/field-team",
    "/api/v1/events",
    "/api/v1/partners",
)

AGENT_IDS = (
    "agent_neema",
    "agent_joseph",
    "agent_mamadou",
    "agent_airport",
    "agent_karicel",
    "agent_essa",
    "agent_seedy",
)


def request_json(method: str, url: str, payload: dict[str, Any] | None = None, token: str | None = None) -> Any:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def login(base_url: str) -> str:
    response = request_json(
        "POST",
        f"{base_url}/api/v1/auth/login",
        {"email": "admin@example.com", "password": "password"},
    )
    return str(response["access_token"])


def safe_call(label: str, fn: Any) -> None:
    started = time.monotonic()
    try:
        result = fn()
        elapsed_ms = int((time.monotonic() - started) * 1000)
        size = len(result) if isinstance(result, list) else len(result.keys()) if isinstance(result, dict) else 1
        print(f"{datetime.now(UTC).isoformat()} {label} ok items={size} elapsed_ms={elapsed_ms}", flush=True)
    except urllib.error.HTTPError as exc:
        print(f"{datetime.now(UTC).isoformat()} {label} http_error={exc.code} {exc.reason}", flush=True)
    except Exception as exc:  # noqa: BLE001 - this script should keep the demo running.
        print(f"{datetime.now(UTC).isoformat()} {label} error={type(exc).__name__}: {exc}", flush=True)


def create_transaction(base_url: str, token: str) -> None:
    payload = {
        "agent_id": random.choice(AGENT_IDS),
        "customer_phone": f"25677{random.randint(1000000, 9999999)}",
        "transaction_type": random.choice(["deposit", "withdrawal", "airtime", "registration"]),
        "amount": random.randint(500, 25_000),
    }
    safe_call("POST /api/v1/transactions", lambda: request_json("POST", f"{base_url}/api/v1/transactions", payload, token))


def create_and_review_float(base_url: str, token: str) -> None:
    payload = {
        "agent_id": random.choice(AGENT_IDS),
        "amount": random.choice([3000, 5000, 10000, 15000, 20000]),
        "request_type": random.choice(["float", "cash"]),
    }
    try:
        created = request_json("POST", f"{base_url}/api/v1/float/requests", payload, token)
    except urllib.error.HTTPError as exc:
        print(f"{datetime.now(UTC).isoformat()} POST /api/v1/float/requests http_error={exc.code} {exc.reason}", flush=True)
        return
    except Exception as exc:  # noqa: BLE001 - this script should keep the demo running.
        print(f"{datetime.now(UTC).isoformat()} POST /api/v1/float/requests error={type(exc).__name__}: {exc}", flush=True)
        return
    print(f"{datetime.now(UTC).isoformat()} POST /api/v1/float/requests ok id={created['id']}", flush=True)
    action = "approve" if random.random() < 0.75 else "reject"
    review_payload = {"reviewer": "e2e-demo"}
    safe_call(
        f"POST /api/v1/float/requests/{created['id']}/{action}",
        lambda: request_json("POST", f"{base_url}/api/v1/float/requests/{created['id']}/{action}", review_payload, token),
    )


def review_kyc(base_url: str, token: str) -> None:
    customers = request_json("GET", f"{base_url}/api/v1/customers", token=token)
    if not customers:
        print(f"{datetime.now(UTC).isoformat()} POST /api/v1/kyc/reviews skipped no customers", flush=True)
        return
    customer = random.choice(customers)
    payload = {
        "customer_id": customer["id"],
        "status": random.choice(["approved", "pending", "rejected"]),
        "reviewer": "e2e-demo",
        "comments": "Automated endpoint exercise",
    }
    safe_call("POST /api/v1/kyc/reviews", lambda: request_json("POST", f"{base_url}/api/v1/kyc/reviews", payload, token))


def poll_read_endpoints(base_url: str, token: str) -> None:
    for path in READ_ENDPOINTS:
        safe_call(f"GET {path}", lambda path=path: request_json("GET", f"{base_url}{path}", token=token))


def run(base_url: str, duration_seconds: int, interval_seconds: float) -> None:
    token = login(base_url)
    deadline = time.monotonic() + duration_seconds
    cycle = 0
    while time.monotonic() < deadline:
        cycle += 1
        print(f"{datetime.now(UTC).isoformat()} endpoint_cycle={cycle}", flush=True)
        poll_read_endpoints(base_url, token)
        create_transaction(base_url, token)
        create_and_review_float(base_url, token)
        review_kyc(base_url, token)
        sleep_for = min(interval_seconds, max(deadline - time.monotonic(), 0))
        if sleep_for > 0:
            time.sleep(sleep_for)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exercise the live API endpoints during an end-to-end demo.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--duration-seconds", type=int, default=900)
    parser.add_argument("--interval-seconds", type=float, default=20.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(args.base_url, args.duration_seconds, args.interval_seconds)


if __name__ == "__main__":
    main()
