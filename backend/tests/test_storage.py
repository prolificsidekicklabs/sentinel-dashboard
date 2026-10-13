from __future__ import annotations

import base64
import os
import sqlite3

import pytest

from sentinel_core.storage import (
    ActivePaperOrderConflict,
    DurableStore,
    IdempotencyConflict,
    StorageIntegrityError,
    StorageNotConfigured,
)


def _key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii").rstrip("=")


def test_credentials_are_encrypted_at_rest_and_scoped_to_the_owner(tmp_path, monkeypatch) -> None:
    database = tmp_path / "secure" / "sentinel.sqlite3"
    store = DurableStore(database)
    monkeypatch.setenv("SENTINEL_VAULT_MASTER_KEY", _key())
    secret = {"key_id": "paper-id-123", "secret_key": "paper-secret-456"}

    store.put_credential("owner-one", "alpaca", secret)
    assert store.get_credential("owner-one", "alpaca") == secret
    assert store.get_credential("owner-two", "alpaca") is None
    with sqlite3.connect(database) as connection:
        ciphertext = connection.execute("SELECT ciphertext FROM encrypted_credentials").fetchone()[
            0
        ]
    assert b"paper-secret-456" not in ciphertext
    assert database.stat().st_mode & 0o777 == 0o600
    assert store.verify_audit_chain()
    events = store.list_audit_events("owner-one")
    assert events[0]["event_type"] == "credential.accessed"
    assert events[1]["event_type"] == "credential.updated"


def test_credentials_fail_closed_without_key_or_on_wrong_key(tmp_path, monkeypatch) -> None:
    store = DurableStore(tmp_path / "sentinel.sqlite3")
    monkeypatch.delenv("SENTINEL_VAULT_MASTER_KEY", raising=False)
    with pytest.raises(StorageNotConfigured):
        store.put_credential("owner", "alpaca", {"secret_key": "never-store-plain"})
    first_key = _key()
    monkeypatch.setenv("SENTINEL_VAULT_MASTER_KEY", first_key)
    store.put_credential("owner", "alpaca", {"secret_key": "protected"})
    monkeypatch.setenv("SENTINEL_VAULT_MASTER_KEY", _key())
    with pytest.raises(StorageIntegrityError):
        store.get_credential("owner", "alpaca")


def test_audit_events_are_append_only_and_hash_chain_detects_tampering(tmp_path) -> None:
    database = tmp_path / "sentinel.sqlite3"
    store = DurableStore(database)
    store.append_audit_event("owner", "test.one", {"value": 1})
    store.append_audit_event("owner", "test.two", {"value": 2})
    assert store.verify_audit_chain()
    with sqlite3.connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE audit_events SET event_type = 'changed' WHERE sequence = 1")
        connection.execute("DROP TRIGGER audit_events_no_update")
        connection.execute(
            "UPDATE audit_events SET payload_json = '{\"value\":9}' WHERE sequence = 1"
        )
    assert not store.verify_audit_chain()


def test_durable_store_rejects_ephemeral_memory_database() -> None:
    with pytest.raises(ValueError, match="file-backed"):
        DurableStore(":memory:")


def test_malformed_audit_payload_fails_integrity_verification(tmp_path) -> None:
    database = tmp_path / "sentinel.sqlite3"
    store = DurableStore(database)
    store.append_audit_event("owner", "test.one", {"value": 1})
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER audit_events_no_update")
        connection.execute("UPDATE audit_events SET payload_json = 'not-json'")
    assert not store.verify_audit_chain()


def test_invalid_audit_chain_blocks_all_business_mutations(tmp_path, monkeypatch) -> None:
    database = tmp_path / "sentinel.sqlite3"
    store = DurableStore(database)
    store.append_audit_event("owner", "test.one", {"value": 1})
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER audit_events_no_update")
        connection.execute("UPDATE audit_events SET payload_json = '{\"value\":9}'")

    monkeypatch.setenv("SENTINEL_VAULT_MASTER_KEY", _key())
    with pytest.raises(StorageIntegrityError):
        store.append_audit_event("owner", "test.two", {"value": 2})
    with pytest.raises(StorageIntegrityError):
        store.put_credential("owner", "alpaca", {"secret_key": "protected"})
    with pytest.raises(StorageIntegrityError):
        store.save_experiment(
            run_id="run-1",
            owner_id="owner",
            strategy_id="sma-test",
            source_id="alpaca:iex",
            dataset_sha256="a" * 64,
            parameters={},
            result={},
        )
    with pytest.raises(StorageIntegrityError):
        store.create_paper_order(
            owner_id="owner",
            idempotency_key="attempt-0001",
            client_order_id="sentinel-client-1",
            request={"symbol": "SPY"},
        )
    with pytest.raises(StorageIntegrityError):
        store.update_paper_order("owner", "attempt-0001", "rejected", {})

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM encrypted_credentials").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM experiment_runs").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM paper_orders").fetchone()[0] == 0


def test_experiments_and_paper_orders_are_durable_and_idempotent(tmp_path) -> None:
    store = DurableStore(tmp_path / "sentinel.sqlite3")
    store.save_experiment(
        run_id="run-1",
        owner_id="owner-one",
        strategy_id="sma-test",
        source_id="alpaca:iex",
        dataset_sha256="a" * 64,
        parameters={"fast": 3},
        result={"return": 0.1},
    )
    assert store.get_experiment("owner-one", "run-1")["result"] == {"return": 0.1}
    assert store.get_experiment("owner-two", "run-1") is None

    order, created = store.create_paper_order(
        owner_id="owner-one",
        idempotency_key="attempt-0001",
        client_order_id="sentinel-client-1",
        request={"symbol": "SPY", "quantity": "1"},
    )
    replay, was_created = store.create_paper_order(
        owner_id="owner-one",
        idempotency_key="attempt-0001",
        client_order_id="sentinel-client-1",
        request={"symbol": "SPY", "quantity": "1"},
    )
    assert created and not was_created
    assert replay["client_order_id"] == order["client_order_id"]
    assert store.list_active_paper_orders("owner-one")[0]["status"] == "submitting"
    with pytest.raises(ActivePaperOrderConflict):
        store.create_paper_order(
            owner_id="owner-one",
            idempotency_key="attempt-0002",
            client_order_id="sentinel-client-2",
            request={"symbol": "QQQ", "quantity": "1"},
        )
    store.update_paper_order(
        "owner-one", "attempt-0001", "filled", {"id": "broker-1", "status": "filled"}
    )
    next_order, next_created = store.create_paper_order(
        owner_id="owner-one",
        idempotency_key="attempt-0002",
        client_order_id="sentinel-client-2",
        request={"symbol": "QQQ", "quantity": "1"},
    )
    assert next_created and next_order["status"] == "submitting"
    with pytest.raises(IdempotencyConflict):
        store.create_paper_order(
            owner_id="owner-one",
            idempotency_key="attempt-0001",
            client_order_id="sentinel-client-1",
            request={"symbol": "QQQ", "quantity": "2"},
        )
    assert store.verify_audit_chain()
