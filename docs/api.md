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

Masking applies to customer lists, KYC review responses, transaction lists, agent reports, and event audit payloads. The operational database retains source values for authorized back-office workflows.

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
- `GET /partners`
- `POST /integrations/telco-transactions`
- `POST /integrations/bank-settlements`
- `POST /integrations/reconcile-settlement`
