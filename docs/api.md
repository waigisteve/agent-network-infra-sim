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

