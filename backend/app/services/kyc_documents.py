from __future__ import annotations

import hashlib
import re
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path

from minio import Minio

from backend.app.config import settings


ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
}
ALLOWED_DOCUMENT_TYPES = {"customer_photo", "national_id_front", "national_id_back", "proof_of_address", "other"}


@dataclass(frozen=True)
class StoredKycDocument:
    storage_backend: str
    storage_key: str
    sha256_hash: str
    mime_type: str
    file_size_bytes: int


def _safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-")
    return cleaned[:80] or "unknown"


def validate_document_type(document_type: str) -> None:
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        allowed = ", ".join(sorted(ALLOWED_DOCUMENT_TYPES))
        raise ValueError(f"document_type must be one of: {allowed}")


def store_kyc_document(customer_id: str, original_filename: str, content_type: str | None, data: bytes) -> StoredKycDocument:
    validate_kyc_file(original_filename, content_type, data)
    if settings.kyc_storage_backend == "minio":
        return store_kyc_document_minio(customer_id, original_filename, content_type or "", data)
    if settings.kyc_storage_backend == "local":
        return store_kyc_document_local(customer_id, original_filename, content_type or "", data)
    raise ValueError("KYC_STORAGE_BACKEND must be either 'local' or 'minio'")


def validate_kyc_file(original_filename: str, content_type: str | None, data: bytes) -> None:
    if not data:
        raise ValueError("uploaded file is empty")
    if len(data) > settings.kyc_max_upload_bytes:
        raise ValueError(f"uploaded file exceeds {settings.kyc_max_upload_bytes} bytes")
    if content_type not in ALLOWED_MIME_TYPES:
        allowed = ", ".join(sorted(ALLOWED_MIME_TYPES))
        raise ValueError(f"unsupported content type; allowed: {allowed}")

    expected_suffix = ALLOWED_MIME_TYPES[content_type]
    filename_suffix = Path(original_filename).suffix.lower()
    if filename_suffix not in {expected_suffix, ".jpeg" if expected_suffix == ".jpg" else expected_suffix}:
        raise ValueError(f"file extension must match content type {content_type}")


def _storage_key(customer_id: str, original_filename: str, sha256_hash: str, content_type: str) -> str:
    expected_suffix = ALLOWED_MIME_TYPES[content_type]
    customer_segment = _safe_segment(customer_id)
    filename_segment = _safe_segment(Path(original_filename).stem)
    return (Path(customer_segment) / f"{sha256_hash[:16]}-{filename_segment}{expected_suffix}").as_posix()


def store_kyc_document_local(customer_id: str, original_filename: str, content_type: str, data: bytes) -> StoredKycDocument:
    sha256_hash = hashlib.sha256(data).hexdigest()
    storage_key = _storage_key(customer_id, original_filename, sha256_hash, content_type)
    storage_root = Path(settings.kyc_storage_path)
    destination = storage_root / storage_key
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)

    return StoredKycDocument(
        storage_backend="local",
        storage_key=storage_key,
        sha256_hash=sha256_hash,
        mime_type=content_type,
        file_size_bytes=len(data),
    )


def store_kyc_document_minio(customer_id: str, original_filename: str, content_type: str, data: bytes) -> StoredKycDocument:
    sha256_hash = hashlib.sha256(data).hexdigest()
    storage_key = _storage_key(customer_id, original_filename, sha256_hash, content_type)
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)
    client.put_object(
        settings.minio_bucket,
        storage_key,
        BytesIO(data),
        length=len(data),
        content_type=content_type,
        metadata={"sha256": sha256_hash, "customer_id": customer_id},
    )
    return StoredKycDocument(
        storage_backend="minio",
        storage_key=storage_key,
        sha256_hash=sha256_hash,
        mime_type=content_type,
        file_size_bytes=len(data),
    )
