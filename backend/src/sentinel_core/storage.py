"""Durable local persistence for encrypted credentials, audit, research, and paper orders.

SQLite is a single-node foundation. Production multi-instance deployments should use a
managed database and a managed KMS; the encryption key is never stored in this database.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_KEY_ENV = "SENTINEL_VAULT_MASTER_KEY"
_PROVIDER_RE = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
ACTIVE_PAPER_ORDER_STATUSES = frozenset(
    {
        "submitting",
        "unknown",
        "new",
        "accepted",
        "pending_new",
        "partially_filled",
        "pending_cancel",
        "pending_replace",
        "accepted_for_bidding",
        "done_for_day",
        "stopped",
        "suspended",
        "calculated",
    }
)
VALID_PAPER_ORDER_STATUSES = ACTIVE_PAPER_ORDER_STATUSES | frozenset(
    {"filled", "canceled", "expired", "replaced", "rejected"}
)


class StorageError(RuntimeError):
    """Base class for persistence failures that must not expose stored values."""


class StorageNotConfigured(StorageError):
    """Raised when encrypted credential storage has no valid master key."""


class StorageIntegrityError(StorageError):
    """Raised when encrypted credentials or an audit chain fail integrity checks."""


class IdempotencyConflict(StorageError):
    """Raised when a client reuses an idempotency key for different order parameters."""


class ActivePaperOrderConflict(StorageError):
    """Raised when a user already has a non-terminal paper order in flight."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _load_master_key(environ: dict[str, str] | None = None) -> bytes:
    values = os.environ if environ is None else environ
    encoded = values.get(_KEY_ENV, "").strip()
    if not encoded:
        raise StorageNotConfigured("credential encryption is not configured")
    try:
        key = base64.b64decode(
            (encoded + "=" * (-len(encoded) % 4)).encode("ascii"),
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise StorageNotConfigured("credential encryption key is invalid") from exc
    if len(key) != 32:
        raise StorageNotConfigured("credential encryption key must encode 32 bytes")
    return key


class DurableStore:
    """SQLite-backed durable event, vault, experiment, and paper-order store."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        if self.database_path == ":memory:":
            raise ValueError("durable storage requires a file-backed SQLite database")
        requested_path = Path(self.database_path).expanduser()
        if requested_path.is_symlink():
            raise ValueError("database path must not be a symlink")
        path = requested_path.resolve()
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.exists() and not path.is_file():
            raise ValueError("database path must be a regular file")
        if not path.exists():
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
        else:
            os.chmod(path, 0o600)
        self.database_path = str(path)
        self._initialize()

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None) -> DurableStore:
        values = os.environ if environ is None else environ
        path = values.get("SENTINEL_DATABASE_PATH", "./var/sentinel.sqlite3")
        return cls(path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = FULL")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    owner_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE TRIGGER IF NOT EXISTS audit_events_no_update
                BEFORE UPDATE ON audit_events
                BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
                BEFORE DELETE ON audit_events
                BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END;
                CREATE TABLE IF NOT EXISTS encrypted_credentials (
                    owner_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    nonce BLOB NOT NULL,
                    ciphertext BLOB NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (owner_id, provider)
                );
                CREATE TABLE IF NOT EXISTS experiment_runs (
                    run_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    dataset_sha256 TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS paper_orders (
                    owner_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    client_order_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (owner_id, idempotency_key),
                    UNIQUE (client_order_id)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS paper_orders_one_active_per_owner
                ON paper_orders(owner_id)
                WHERE status IN (
                    'submitting', 'unknown', 'new', 'accepted', 'pending_new',
                    'partially_filled', 'pending_cancel', 'pending_replace',
                    'accepted_for_bidding', 'done_for_day', 'stopped', 'suspended', 'calculated'
                );
                """
            )

    @staticmethod
    def _append_event(
        connection: sqlite3.Connection,
        *,
        owner_id: str,
        event_type: str,
        payload: dict[str, Any],
        created_at: str | None = None,
    ) -> str:
        event_id = secrets.token_hex(16)
        timestamp = created_at or _utc_now()
        payload_json = _canonical_json(payload)
        row = connection.execute(
            "SELECT event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = str(row["event_hash"]) if row is not None else ""
        body = {
            "created_at": timestamp,
            "event_id": event_id,
            "event_type": event_type,
            "owner_id": owner_id,
            "payload": payload,
            "previous_hash": previous_hash,
        }
        event_hash = hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()
        connection.execute(
            "INSERT INTO audit_events(event_id, owner_id, event_type, created_at, "
            "payload_json, previous_hash, event_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event_id,
                owner_id,
                event_type,
                timestamp,
                payload_json,
                previous_hash or None,
                event_hash,
            ),
        )
        return event_id

    def append_audit_event(self, owner_id: str, event_type: str, payload: dict[str, Any]) -> str:
        if not owner_id or not event_type or len(event_type) > 120:
            raise ValueError("audit event identity is invalid")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_valid_audit_chain(connection)
            return self._append_event(
                connection, owner_id=owner_id, event_type=event_type, payload=payload
            )

    @staticmethod
    def _audit_chain_is_valid(connection: sqlite3.Connection) -> bool:
        previous_hash = ""
        try:
            rows = connection.execute("SELECT * FROM audit_events ORDER BY sequence ASC").fetchall()
            for row in rows:
                payload = json.loads(str(row["payload_json"]))
                body = {
                    "created_at": str(row["created_at"]),
                    "event_id": str(row["event_id"]),
                    "event_type": str(row["event_type"]),
                    "owner_id": str(row["owner_id"]),
                    "payload": payload,
                    "previous_hash": previous_hash,
                }
                expected = hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()
                stored_previous = str(row["previous_hash"] or "")
                if stored_previous != previous_hash or not secrets.compare_digest(
                    expected, str(row["event_hash"])
                ):
                    return False
                previous_hash = expected
        except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError):
            return False
        return True

    @classmethod
    def _require_valid_audit_chain(cls, connection: sqlite3.Connection) -> None:
        if not cls._audit_chain_is_valid(connection):
            raise StorageIntegrityError("audit ledger failed integrity verification")

    def verify_audit_chain(self) -> bool:
        try:
            with self._connect() as connection:
                return self._audit_chain_is_valid(connection)
        except sqlite3.Error:
            return False

    def list_audit_events(self, owner_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError("audit limit is outside safe bounds")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT event_id, event_type, created_at, payload_json, event_hash "
                "FROM audit_events WHERE owner_id = ? ORDER BY sequence DESC LIMIT ?",
                (owner_id, limit),
            ).fetchall()
        return [
            {
                "event_id": str(row["event_id"]),
                "event_type": str(row["event_type"]),
                "created_at": str(row["created_at"]),
                "payload": json.loads(str(row["payload_json"])),
                "event_hash": str(row["event_hash"]),
            }
            for row in rows
        ]

    def put_credential(
        self,
        owner_id: str,
        provider: str,
        credential: dict[str, str],
        *,
        environ: dict[str, str] | None = None,
    ) -> None:
        if not owner_id or not _PROVIDER_RE.fullmatch(provider):
            raise ValueError("credential owner or provider is invalid")
        if not credential or any(
            not isinstance(value, str) or not value for value in credential.values()
        ):
            raise ValueError("credential payload must contain non-empty string fields")
        plaintext = _canonical_json(credential).encode("utf-8")
        if len(plaintext) > 16_384:
            raise ValueError("credential payload exceeds its size limit")
        key = _load_master_key(environ)
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, f"{owner_id}:{provider}".encode())
        timestamp = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_valid_audit_chain(connection)
            connection.execute(
                "INSERT INTO encrypted_credentials(owner_id, provider, nonce, ciphertext, "
                "updated_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(owner_id, provider) "
                "DO UPDATE SET nonce=excluded.nonce, ciphertext=excluded.ciphertext, "
                "updated_at=excluded.updated_at",
                (owner_id, provider, nonce, ciphertext, timestamp),
            )
            self._append_event(
                connection,
                owner_id=owner_id,
                event_type="credential.updated",
                payload={"provider": provider, "updated_at": timestamp},
                created_at=timestamp,
            )

    def get_credential(
        self,
        owner_id: str,
        provider: str,
        *,
        environ: dict[str, str] | None = None,
    ) -> dict[str, str] | None:
        key = _load_master_key(environ)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT nonce, ciphertext FROM encrypted_credentials "
                "WHERE owner_id = ? AND provider = ?",
                (owner_id, provider),
            ).fetchone()
            if row is None:
                return None
            try:
                plaintext = AESGCM(key).decrypt(
                    bytes(row["nonce"]),
                    bytes(row["ciphertext"]),
                    f"{owner_id}:{provider}".encode(),
                )
                result = json.loads(plaintext)
            except (InvalidTag, json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
                raise StorageIntegrityError(
                    "stored credential failed integrity verification"
                ) from exc
        if not isinstance(result, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in result.items()
        ):
            raise StorageIntegrityError("stored credential has an invalid schema")
        self.append_audit_event(owner_id, "credential.accessed", {"provider": provider})
        return result

    def delete_credential(self, owner_id: str, provider: str) -> bool:
        timestamp = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_valid_audit_chain(connection)
            result = connection.execute(
                "DELETE FROM encrypted_credentials WHERE owner_id = ? AND provider = ?",
                (owner_id, provider),
            )
            if result.rowcount:
                self._append_event(
                    connection,
                    owner_id=owner_id,
                    event_type="credential.deleted",
                    payload={"provider": provider, "deleted_at": timestamp},
                    created_at=timestamp,
                )
                return True
            return False

    def credential_exists(self, owner_id: str, provider: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM encrypted_credentials WHERE owner_id = ? AND provider = ?",
                (owner_id, provider),
            ).fetchone()
        return row is not None

    def save_experiment(
        self,
        *,
        run_id: str,
        owner_id: str,
        strategy_id: str,
        source_id: str,
        dataset_sha256: str,
        parameters: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        timestamp = _utc_now()
        parameters_json = _canonical_json(parameters)
        result_json = _canonical_json(result)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_valid_audit_chain(connection)
            existing = connection.execute(
                "SELECT dataset_sha256 FROM experiment_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if existing is not None:
                if str(existing["dataset_sha256"]) != dataset_sha256:
                    raise StorageIntegrityError("experiment identifier collision")
                return
            connection.execute(
                "INSERT INTO experiment_runs(run_id, owner_id, created_at, strategy_id, "
                "source_id, dataset_sha256, parameters_json, result_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    owner_id,
                    timestamp,
                    strategy_id,
                    source_id,
                    dataset_sha256,
                    parameters_json,
                    result_json,
                ),
            )
            self._append_event(
                connection,
                owner_id=owner_id,
                event_type="research.backtest.completed",
                payload={
                    "run_id": run_id,
                    "strategy_id": strategy_id,
                    "source_id": source_id,
                    "dataset_sha256": dataset_sha256,
                },
                created_at=timestamp,
            )

    def get_experiment(self, owner_id: str, run_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT run_id, created_at, strategy_id, source_id, dataset_sha256, "
                "parameters_json, result_json "
                "FROM experiment_runs WHERE owner_id = ? AND run_id = ?",
                (owner_id, run_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "run_id": str(row["run_id"]),
            "created_at": str(row["created_at"]),
            "strategy_id": str(row["strategy_id"]),
            "source_id": str(row["source_id"]),
            "dataset_sha256": str(row["dataset_sha256"]),
            "parameters": json.loads(str(row["parameters_json"])),
            "result": json.loads(str(row["result_json"])),
        }

    def create_paper_order(
        self,
        *,
        owner_id: str,
        idempotency_key: str,
        client_order_id: str,
        request: dict[str, Any],
        risk_evaluation_id: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        if risk_evaluation_id is not None and not risk_evaluation_id.strip():
            raise ValueError("risk evaluation identifier must not be empty")
        request_json = _canonical_json(request)
        timestamp = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_valid_audit_chain(connection)
            existing = connection.execute(
                "SELECT * FROM paper_orders WHERE owner_id = ? AND idempotency_key = ?",
                (owner_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if str(existing["request_json"]) != request_json:
                    raise IdempotencyConflict(
                        "idempotency key was already used for a different request"
                    )
                return self._order_row(existing), False
            try:
                connection.execute(
                    "INSERT INTO paper_orders(owner_id, idempotency_key, client_order_id, "
                    "status, request_json, response_json, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'submitting', ?, NULL, ?, ?)",
                    (
                        owner_id,
                        idempotency_key,
                        client_order_id,
                        request_json,
                        timestamp,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ActivePaperOrderConflict(
                    "another paper order is already active for this user"
                ) from exc
            self._append_event(
                connection,
                owner_id=owner_id,
                event_type="paper.order.submitting",
                payload={
                    "client_order_id": client_order_id,
                    "request": request,
                    "risk_evaluation_id": risk_evaluation_id,
                },
                created_at=timestamp,
            )
            row = connection.execute(
                "SELECT * FROM paper_orders WHERE owner_id = ? AND idempotency_key = ?",
                (owner_id, idempotency_key),
            ).fetchone()
        if row is None:
            raise StorageError("paper order persistence failed")
        return self._order_row(row), True

    @staticmethod
    def _order_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "owner_id": str(row["owner_id"]),
            "idempotency_key": str(row["idempotency_key"]),
            "client_order_id": str(row["client_order_id"]),
            "status": str(row["status"]),
            "request": json.loads(str(row["request_json"])),
            "response": json.loads(str(row["response_json"])) if row["response_json"] else None,
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    def update_paper_order(
        self, owner_id: str, idempotency_key: str, status: str, response: dict[str, Any]
    ) -> dict[str, Any] | None:
        if status not in VALID_PAPER_ORDER_STATUSES:
            raise ValueError("paper broker returned an unsupported order state")
        timestamp = _utc_now()
        response_json = _canonical_json(response)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_valid_audit_chain(connection)
            connection.execute(
                "UPDATE paper_orders SET status = ?, response_json = ?, updated_at = ? "
                "WHERE owner_id = ? AND idempotency_key = ?",
                (status, response_json, timestamp, owner_id, idempotency_key),
            )
            row = connection.execute(
                "SELECT * FROM paper_orders WHERE owner_id = ? AND idempotency_key = ?",
                (owner_id, idempotency_key),
            ).fetchone()
            if row is None:
                return None
            order = self._order_row(row)
            self._append_event(
                connection,
                owner_id=owner_id,
                event_type="paper.order.updated",
                payload={"client_order_id": order["client_order_id"], "status": status},
                created_at=timestamp,
            )
            return order

    def get_paper_order(self, owner_id: str, idempotency_key: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM paper_orders WHERE owner_id = ? AND idempotency_key = ?",
                (owner_id, idempotency_key),
            ).fetchone()
        return self._order_row(row) if row is not None else None

    def list_active_paper_orders(self, owner_id: str) -> list[dict[str, Any]]:
        statuses = tuple(sorted(ACTIVE_PAPER_ORDER_STATUSES))
        placeholders = ", ".join("?" for _ in statuses)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM paper_orders WHERE owner_id = ? AND status IN ({placeholders}) "
                "ORDER BY created_at ASC",
                (owner_id, *statuses),
            ).fetchall()
        return [self._order_row(row) for row in rows]


__all__ = [
    "DurableStore",
    "ActivePaperOrderConflict",
    "ACTIVE_PAPER_ORDER_STATUSES",
    "IdempotencyConflict",
    "StorageError",
    "StorageIntegrityError",
    "StorageNotConfigured",
]
