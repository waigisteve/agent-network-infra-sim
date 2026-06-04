#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_FRONTEND_URL = "http://127.0.0.1:5173"
DEFAULT_REDPANDA_CONSOLE_URL = "http://127.0.0.1:18081"
DEFAULT_AIRFLOW_URL = "http://127.0.0.1:18080"
DEFAULT_SUPERSET_URL = "http://127.0.0.1:18088"
DEFAULT_KAFKA_HOST = "127.0.0.1"
DEFAULT_KAFKA_PORT = 19092
DEFAULT_TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str
    required: bool = True

    @property
    def failed(self) -> bool:
        return self.required and self.status != "ok"


def http_json(url: str, timeout_seconds: int) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
        return response.status, payload


def http_text(url: str, timeout_seconds: int) -> tuple[int, str]:
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.status, response.read(512).decode("utf-8", errors="replace")


def post_json(url: str, payload: dict[str, Any], timeout_seconds: int, token: str | None = None) -> tuple[int, dict[str, Any]]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def get_json(url: str, timeout_seconds: int, token: str | None = None) -> tuple[int, dict[str, Any]]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def check_api_health(api_base_url: str, timeout_seconds: int) -> CheckResult:
    try:
        status, payload = http_json(f"{api_base_url}/health", timeout_seconds)
    except Exception as exc:
        return CheckResult("api.health", "fail", str(exc))
    if status == 200 and payload == {"status": "ok"}:
        return CheckResult("api.health", "ok", f"{api_base_url}/health returned ok")
    return CheckResult("api.health", "fail", f"unexpected response: HTTP {status} {payload}")


def check_api_readiness(api_base_url: str, timeout_seconds: int) -> CheckResult:
    try:
        status, payload = http_json(f"{api_base_url}/ready", timeout_seconds)
    except Exception as exc:
        return CheckResult("api.ready", "fail", str(exc))
    if status == 200 and payload.get("database") == "ok":
        kafka = payload.get("kafka", "unknown")
        return CheckResult("api.ready", "ok", f"database ok, kafka {kafka}")
    return CheckResult("api.ready", "fail", f"unexpected response: HTTP {status} {payload}")


def check_auth_flow(api_base_url: str, timeout_seconds: int) -> CheckResult:
    try:
        status, payload = post_json(
            f"{api_base_url}/api/v1/auth/login",
            {"email": "admin@example.com", "password": "password"},
            timeout_seconds,
        )
        token = payload.get("access_token")
        if status != 200 or not isinstance(token, str) or not token:
            return CheckResult("api.auth", "fail", f"login did not return a token: HTTP {status} {payload}")
        me_status, me_payload = get_json(f"{api_base_url}/api/v1/me", timeout_seconds, token)
    except Exception as exc:
        return CheckResult("api.auth", "fail", str(exc))
    if me_status == 200 and me_payload.get("role") == "admin":
        return CheckResult("api.auth", "ok", "seeded admin login and protected route succeeded")
    return CheckResult("api.auth", "fail", f"protected route failed: HTTP {me_status} {me_payload}")


def check_frontend(frontend_url: str, timeout_seconds: int) -> CheckResult:
    try:
        status, body = http_text(frontend_url, timeout_seconds)
    except Exception as exc:
        return CheckResult("frontend", "fail", str(exc))
    if status == 200 and ("Agent Network" in body or "<div id=\"root\"" in body):
        return CheckResult("frontend", "ok", f"{frontend_url} returned application shell")
    return CheckResult("frontend", "fail", f"unexpected response: HTTP {status}")


def check_tcp_port(name: str, host: str, port: int, timeout_seconds: int, required: bool = True) -> CheckResult:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return CheckResult(name, "ok", f"{host}:{port} reachable", required=required)
    except OSError as exc:
        status = "fail" if required else "skip"
        return CheckResult(name, status, f"{host}:{port} unreachable: {exc}", required=required)


def check_optional_http(name: str, url: str, timeout_seconds: int) -> CheckResult:
    try:
        status, _ = http_text(url, timeout_seconds)
    except Exception as exc:
        return CheckResult(name, "skip", f"optional service not reachable: {exc}", required=False)
    if 200 <= status < 500:
        return CheckResult(name, "ok", f"{url} reachable", required=False)
    return CheckResult(name, "skip", f"optional service returned HTTP {status}", required=False)


def check_docker_services() -> CheckResult:
    expected = {"postgres", "redpanda", "api", "worker", "frontend"}
    try:
        process = subprocess.run(
            ["docker", "compose", "ps", "--services", "--status", "running"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return CheckResult("docker.services", "fail", str(exc))
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip() or "docker compose ps failed"
        return CheckResult("docker.services", "fail", detail)
    running = {line.strip() for line in process.stdout.splitlines() if line.strip()}
    missing = sorted(expected - running)
    if missing:
        return CheckResult("docker.services", "fail", f"missing running services: {', '.join(missing)}")
    return CheckResult("docker.services", "ok", f"running services include: {', '.join(sorted(expected))}")


def check_dbt_project(repo_root: Path) -> CheckResult:
    required_paths = [
        repo_root / "dbt" / "dbt_project.yml",
        repo_root / "dbt" / "profiles" / "profiles.yml",
        repo_root / "dbt" / "models",
    ]
    missing = [str(path.relative_to(repo_root)) for path in required_paths if not path.exists()]
    if missing:
        return CheckResult("dbt.project", "fail", f"missing: {', '.join(missing)}")
    return CheckResult("dbt.project", "ok", "dbt project, profile, and models directory exist")


def collect_checks(args: argparse.Namespace) -> list[CheckResult]:
    repo_root = Path(__file__).resolve().parents[1]
    return [
        check_docker_services(),
        check_api_health(args.api_base_url, args.timeout_seconds),
        check_api_readiness(args.api_base_url, args.timeout_seconds),
        check_auth_flow(args.api_base_url, args.timeout_seconds),
        check_frontend(args.frontend_url, args.timeout_seconds),
        check_tcp_port("kafka.external", args.kafka_host, args.kafka_port, args.timeout_seconds),
        check_optional_http("redpanda.console", args.redpanda_console_url, args.timeout_seconds),
        check_optional_http("airflow", args.airflow_url, args.timeout_seconds),
        check_optional_http("superset", args.superset_url, args.timeout_seconds),
        check_dbt_project(repo_root),
    ]


def print_results(results: list[CheckResult]) -> None:
    width = max(len(result.name) for result in results)
    for result in results:
        marker = {"ok": "OK", "skip": "SKIP", "fail": "FAIL"}[result.status]
        print(f"{marker:>4}  {result.name:<{width}}  {result.detail}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local platform readiness checks.")
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--frontend-url", default=DEFAULT_FRONTEND_URL)
    parser.add_argument("--redpanda-console-url", default=DEFAULT_REDPANDA_CONSOLE_URL)
    parser.add_argument("--airflow-url", default=DEFAULT_AIRFLOW_URL)
    parser.add_argument("--superset-url", default=DEFAULT_SUPERSET_URL)
    parser.add_argument("--kafka-host", default=DEFAULT_KAFKA_HOST)
    parser.add_argument("--kafka-port", type=int, default=DEFAULT_KAFKA_PORT)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser.parse_args()


def main() -> int:
    results = collect_checks(parse_args())
    print_results(results)
    return 1 if any(result.failed for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
