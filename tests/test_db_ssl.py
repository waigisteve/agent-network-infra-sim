from types import SimpleNamespace

from backend.app import db


def test_database_connect_args_include_postgres_ssl_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        db,
        "settings",
        SimpleNamespace(
            database_url="postgresql+psycopg://agent:secret@postgres:5432/agent_network",
            database_ssl_mode="verify-full",
            database_ssl_root_cert="/certs/ca.pem",
            database_ssl_cert="/certs/client.pem",
            database_ssl_key="/certs/client.key",
        ),
    )

    assert db.database_connect_args() == {
        "sslmode": "verify-full",
        "sslrootcert": "/certs/ca.pem",
        "sslcert": "/certs/client.pem",
        "sslkey": "/certs/client.key",
    }


def test_database_connect_args_keep_sqlite_thread_setting(monkeypatch) -> None:
    monkeypatch.setattr(
        db,
        "settings",
        SimpleNamespace(
            database_url="sqlite:///:memory:",
            database_ssl_mode="require",
            database_ssl_root_cert="/certs/ca.pem",
            database_ssl_cert="/certs/client.pem",
            database_ssl_key="/certs/client.key",
        ),
    )

    assert db.database_connect_args() == {"check_same_thread": False}
