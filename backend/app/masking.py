from __future__ import annotations

from typing import Any


SENSITIVE_KEYS = {"phone", "customer_phone", "national_id", "address", "birthday", "name", "surname", "full_name"}


def mask_phone(value: str | None) -> str | None:
    if not value:
        return value
    visible = value[-3:] if len(value) > 3 else value[-1:]
    return f"{'*' * max(len(value) - len(visible), 0)}{visible}"


def mask_identifier(value: str | None) -> str | None:
    if not value:
        return value
    visible = value[-4:] if len(value) > 4 else value[-1:]
    return f"{'*' * max(len(value) - len(visible), 0)}{visible}"


def mask_name(value: str | None) -> str | None:
    if not value:
        return value
    return f"{value[:1]}***"


def mask_address(value: str | None) -> str | None:
    if not value:
        return value
    return "masked address"


def mask_customer_record(record: dict[str, Any]) -> dict[str, Any]:
    masked = dict(record)
    if "name" in masked:
        masked["name"] = mask_name(str(masked["name"]))
    if "surname" in masked:
        masked["surname"] = mask_name(str(masked["surname"]))
    if "full_name" in masked:
        parts = str(masked["full_name"]).split()
        masked["full_name"] = " ".join(mask_name(part) or "" for part in parts)
    if "phone" in masked:
        masked["phone"] = mask_phone(str(masked["phone"]))
    if "customer_phone" in masked:
        masked["customer_phone"] = mask_phone(str(masked["customer_phone"]))
    if "national_id" in masked:
        masked["national_id"] = mask_identifier(str(masked["national_id"]))
    if "address" in masked:
        masked["address"] = mask_address(str(masked["address"]))
    if "birthday" in masked:
        masked["birthday"] = "masked"
    return masked


def mask_payload(payload: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            masked[key] = mask_payload(value)
        elif isinstance(value, list):
            masked[key] = [mask_payload(item) if isinstance(item, dict) else item for item in value]
        elif key in {"phone", "customer_phone"}:
            masked[key] = mask_phone(str(value))
        elif key in {"national_id", "id_number"}:
            masked[key] = mask_identifier(str(value))
        elif key in {"address", "birthday"}:
            masked[key] = "masked"
        elif key in {"name", "surname", "full_name", "reviewer"}:
            masked[key] = mask_name(str(value))
        else:
            masked[key] = value
    return masked
