# KYC Document Storage

The current implementation stores KYC document **metadata** in PostgreSQL and stores file bytes in MinIO object storage. A local filesystem adapter remains available for tests and explicit fallback development.

## Current Local Flow

```mermaid
flowchart LR
    reviewer[KYC reviewer/admin] --> api[FastAPI upload endpoint]
    api --> storage[MinIO bucket<br/>kyc-documents]
    api --> metadata[(kyc_documents)]
    api --> event_log[(event_log)]
    api --> kafka[kyc-events]
```

Endpoints:

- `POST /api/v1/kyc/customers/{customer_id}/documents`
- `GET /api/v1/kyc/customers/{customer_id}/documents`

Allowed upload types:

- `image/jpeg`
- `image/png`
- `application/pdf`

Allowed document categories:

- `customer_photo`
- `national_id_front`
- `national_id_back`
- `proof_of_address`
- `other`

## PostgreSQL Metadata

`kyc_documents` stores:

- customer relationship
- document type
- original filename
- storage backend and storage key
- SHA-256 hash
- MIME type and file size
- uploader user ID
- verification status
- review notes and timestamps

The table is covered by forced RLS and role grants. File bytes are not stored in PostgreSQL.

## Local MinIO

Docker Compose starts:

- `minio` at `http://127.0.0.1:9000`
- MinIO Console at `http://127.0.0.1:9001`
- `minio-init`, which creates the private `kyc-documents` bucket

The API uses these environment variables:

```bash
KYC_STORAGE_BACKEND=minio
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=agentminio
MINIO_SECRET_KEY=...
MINIO_BUCKET=kyc-documents
MINIO_SECURE=false
```

For tests or filesystem-only development, set:

```bash
KYC_STORAGE_BACKEND=local
KYC_STORAGE_PATH=storage/kyc
```

## Why Not Store Images In PostgreSQL?

PostgreSQL is the right place for searchable metadata, audit relationships, constraints, and review status. It is usually the wrong place for growing binary object storage because images increase backup size, slow restores, and make lifecycle/retention management harder.

## Production Swap

The MinIO adapter is the local object-storage implementation. In hosted production, the same storage boundary should be backed by the cloud provider object store:

| Environment | Storage backend |
| --- | --- |
| Local development | MinIO bucket `kyc-documents`; optional `storage/kyc` fallback |
| AWS | S3 with SSE-KMS and presigned URLs |
| Azure | Blob Storage with private containers and SAS URLs |
| GCP | Cloud Storage with signed URLs |
| Self-hosted/local object storage | MinIO |

Production requirements:

- private bucket/container
- encryption at rest
- short-lived signed URLs for file access
- malware/content scanning before review
- file hash verification
- audit events for upload, view, approval, rejection, and deletion
- retention policy tied to KYC/data-protection obligations
