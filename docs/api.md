# API

All APIs are under `/api/v1`.

## Auth

- `POST /auth/login`
- `GET /me`

Demo login body:

```json
{"email": "admin@example.com", "password": "password"}
```

Use the returned bearer token for all other endpoints.

## Data Masking

Customer-facing and reporting endpoints mask customer PII in API responses:

- names become initial-only values such as `M***`
- phone numbers expose only the final three digits
- national IDs expose only the final four digits
- addresses return `masked address`
- birthdays return `masked`

Masking applies to customer lists, KYC review responses, transaction lists, agent reports, and event audit payloads, including nested dictionaries and lists in event payloads. The operational database retains source values for authorized back-office workflows.

## Core Resources

- `GET /agents`
- `GET /field-agents`
- `GET /customers`
- `POST /kyc/reviews`
- `GET /float/requests`
- `POST /float/requests`
- `POST /float/requests/{id}/approve`
- `POST /float/requests/{id}/reject`
- `GET /float/reconciliation`
- `GET /transactions`
- `POST /transactions`
- `GET /commissions`
- `GET /reports/agent-network`
- `GET /reports/agent/{agent_id}`
- `GET /maps/field-team`
- `GET /events`
- `GET /stream/readiness`
- `GET /stream/dead-letter-events`
- `GET /security/audit-log`
- `GET /partners`
- `POST /integrations/telco-transactions`
- `POST /integrations/bank-settlements`
- `POST /integrations/reconcile-settlement`

## Endpoint Access Matrix

Public endpoints are limited to liveness/readiness and login. Every operational endpoint under `/api/v1` requires a bearer token.

| Endpoint | Admin | Field agent | Agent | KYC reviewer | Security note |
| --- | --- | --- | --- | --- | --- |
| `GET /health` | Public | Public | Public | Public | Liveness only; returns no business data. |
| `GET /ready` | Public | Public | Public | Public | Local readiness only; production should expose this internally or behind infrastructure health checks. |
| `POST /api/v1/auth/login` | Public | Public | Public | Public | Issues JWT for seeded demo users. |
| `GET /api/v1/me` | Yes | Yes | Yes | Yes | Returns current user identity and role. |
| `GET /api/v1/agents` | Yes | Yes | Own agent filtered | Yes | Agent role is constrained to its assigned `agent_id`. |
| `GET /api/v1/field-agents` | Yes | Yes | No | No | Field-management scope. |
| `GET /api/v1/customers` | Yes | Yes | Yes | Yes | PII is masked in API responses. |
| `POST /api/v1/kyc/reviews` | Yes | No | No | Yes | KYC decision scope only. |
| `GET /api/v1/float/requests` | Yes | Yes | Yes | Yes | Read-only operational queue. |
| `POST /api/v1/float/requests` | Yes | No | Yes | No | Agent submissions are forced to the caller's assigned `agent_id`. |
| `POST /api/v1/float/requests/{id}/approve` | Yes | No | No | No | Admin approval only. |
| `POST /api/v1/float/requests/{id}/reject` | Yes | No | No | No | Admin rejection only. |
| `GET /api/v1/float/reconciliation` | Yes | Yes | No | No | Field operations and admin scope. |
| `GET /api/v1/transactions` | Yes | Yes | Own agent filtered | Yes | Customer phone is masked. |
| `POST /api/v1/transactions` | Yes | No | Yes | No | Agent-created transactions are forced to the caller's assigned `agent_id`. |
| `GET /api/v1/commissions` | Yes | Yes | Yes | Yes | Aggregate commission view. |
| `GET /api/v1/reports/agent-network` | Yes | Yes | No | No | Network-level operational reporting. |
| `GET /api/v1/reports/agent/{agent_id}` | Yes | Yes | Own agent only | Yes | Agent role cannot view another agent's report. |
| `GET /api/v1/maps/field-team` | Yes | Yes | No | No | Location-oriented field operations scope. |
| `GET /api/v1/events` | Yes | No | No | No | Admin audit/event stream only; payloads are masked. |
| `GET /api/v1/stream/readiness` | Yes | No | No | No | Admin-only worker health view with consumer offsets, processed counts, failure counts, and open dead-letter totals. |
| `GET /api/v1/stream/dead-letter-events` | Yes | No | No | No | Admin-only stream failure queue; response omits raw customer PII and authorization secrets. |
| `GET /api/v1/security/audit-log` | Yes | No | No | No | Admin security audit stream for failed login and blocked access attempts. |
| `GET /api/v1/partners` | Yes | Yes | No | No | Partner metadata visibility for operations. |
| `POST /api/v1/integrations/telco-transactions` | Yes | No | No | No | Admin-controlled partner feed ingestion. |
| `POST /api/v1/integrations/bank-settlements` | Yes | No | No | No | Admin-controlled settlement feed ingestion. |
| `POST /api/v1/integrations/reconcile-settlement` | Yes | No | No | No | Admin-controlled reconciliation action. |

The access matrix is backed by `tests/test_api_access_matrix.py`, which checks anonymous rejection, role rejection, KYC scope, admin-only integration scope, security audit logging, and agent self-access boundaries.

## Readiness Response

`GET /ready` keeps the original top-level compatibility keys:

```json
{
  "status": "ready",
  "database": "ok",
  "kafka": "enabled"
}
```

It also includes component detail for operational diagnosis:

```json
{
  "components": {
    "database": {"status": "ok", "latency_ms": 1.23},
    "kafka": {"status": "enabled", "bootstrap_servers": "redpanda:9092"},
    "security_audit_log": {"status": "ok", "records": 12}
  }
}
```

In production, `/ready` should be exposed only to infrastructure health checks or protected by the gateway/reverse proxy.
