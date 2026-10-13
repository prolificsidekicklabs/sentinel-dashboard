"""OIDC access-token verification for the Sentinel API.

Only a configured issuer and its configured JWKS endpoint are trusted. This module
never accepts identity claims from browser-supplied headers or unverified JWTs.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
import jwt

_ALLOWED_ALGORITHMS = ("RS256", "ES256", "EdDSA")
_MAX_JWKS_BYTES = 256 * 1024


class AuthConfigurationError(RuntimeError):
    """Raised when production OIDC configuration is missing or invalid."""


class InvalidAccessToken(RuntimeError):
    """Raised when a bearer token cannot be verified against the configured issuer."""


@dataclass(frozen=True, slots=True)
class OIDCSettings:
    issuer: str
    audience: str
    jwks_url: str
    cache_seconds: int = 300
    timeout_seconds: float = 5.0

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None) -> OIDCSettings | None:
        values = os.environ if environ is None else environ
        names = ("SENTINEL_OIDC_ISSUER", "SENTINEL_OIDC_AUDIENCE", "SENTINEL_OIDC_JWKS_URL")
        configured = [values.get(name, "").strip() for name in names]
        if not any(configured):
            return None
        if not all(configured):
            raise AuthConfigurationError(
                "OIDC issuer, audience, and JWKS URL must be configured together"
            )
        issuer, audience, jwks_url = configured
        issuer_parts = urlsplit(issuer)
        jwks_parts = urlsplit(jwks_url)
        if (
            issuer_parts.scheme != "https"
            or not issuer_parts.netloc
            or issuer_parts.username
            or issuer_parts.password
            or issuer_parts.query
            or issuer_parts.fragment
        ):
            raise AuthConfigurationError("OIDC issuer must be an HTTPS origin or issuer URL")
        if (
            jwks_parts.scheme != "https"
            or not jwks_parts.netloc
            or jwks_parts.username
            or jwks_parts.password
            or jwks_parts.query
            or jwks_parts.fragment
        ):
            raise AuthConfigurationError("OIDC JWKS URL must be HTTPS")
        try:
            cache_seconds = int(values.get("SENTINEL_OIDC_JWKS_CACHE_SECONDS", "300"))
            timeout_seconds = float(values.get("SENTINEL_OIDC_TIMEOUT_SECONDS", "5"))
        except ValueError as exc:
            raise AuthConfigurationError("OIDC limits must be numeric") from exc
        if not 30 <= cache_seconds <= 3600 or not 0.2 <= timeout_seconds <= 20:
            raise AuthConfigurationError("OIDC cache and timeout limits are outside safe bounds")
        return cls(issuer, audience, jwks_url, cache_seconds, timeout_seconds)


@dataclass(frozen=True, slots=True)
class Principal:
    """Identity and explicit API scopes derived only from a verified token."""

    owner_id: str
    subject: str
    scopes: frozenset[str]
    auth_method: Literal["oidc", "api-key"]
    issuer: str | None = None

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


class OIDCVerifier:
    """Small bounded JWKS cache and strict JWT verifier for OIDC access tokens."""

    def __init__(
        self,
        settings: OIDCSettings,
        *,
        http_client: httpx.AsyncClient | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.settings = settings
        self.http_client = http_client
        self.clock = clock or time.time
        self._keys: dict[str, dict[str, Any]] = {}
        self._keys_expires_at = 0.0
        self._last_unknown_kid_refresh_at = float("-inf")
        self._lock = asyncio.Lock()

    async def _fetch_jwks(self) -> dict[str, dict[str, Any]]:
        async def fetch(client: httpx.AsyncClient) -> bytes:
            async with client.stream(
                "GET", self.settings.jwks_url, follow_redirects=False
            ) as response:
                response.raise_for_status()
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > _MAX_JWKS_BYTES:
                        raise InvalidAccessToken("issuer key set exceeds its size limit")
                    chunks.append(chunk)
                return b"".join(chunks)

        try:
            if self.http_client is not None:
                raw = await fetch(self.http_client)
            else:
                async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                    raw = await fetch(client)
            document = json.loads(raw)
        except InvalidAccessToken:
            raise
        except (httpx.HTTPError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise InvalidAccessToken("issuer signing keys could not be retrieved") from exc
        if not isinstance(document, dict) or not isinstance(document.get("keys"), list):
            raise InvalidAccessToken("issuer key set has an invalid schema")
        keys: dict[str, dict[str, Any]] = {}
        for item in document["keys"]:
            if not isinstance(item, dict):
                continue
            kid = item.get("kid")
            alg = item.get("alg")
            if (
                isinstance(kid, str)
                and kid
                and len(kid) <= 256
                and (alg is None or alg in _ALLOWED_ALGORITHMS)
                and item.get("use", "sig") == "sig"
            ):
                keys[kid] = item
        if not keys:
            raise InvalidAccessToken("issuer key set contains no usable signing keys")
        return keys

    async def _get_key(self, kid: str, *, force_refresh: bool = False) -> Any:
        async with self._lock:
            now = float(self.clock())
            expired = now >= self._keys_expires_at
            unknown_refresh_due = (
                kid not in self._keys and now - self._last_unknown_kid_refresh_at >= 30
            )
            if force_refresh or expired or unknown_refresh_due:
                self._keys = await self._fetch_jwks()
                self._keys_expires_at = now + self.settings.cache_seconds
                self._last_unknown_kid_refresh_at = now
            jwk = self._keys.get(kid)
            if jwk is None:
                raise InvalidAccessToken("token signing key is not trusted")
        try:
            return jwt.PyJWK.from_dict(jwk).key
        except (jwt.PyJWTError, TypeError, ValueError) as exc:
            raise InvalidAccessToken("issuer signing key is invalid") from exc

    async def verify(self, token: str) -> Principal:
        if not token or len(token) > 16_384:
            raise InvalidAccessToken("bearer token is invalid")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise InvalidAccessToken("bearer token is invalid") from exc
        kid = header.get("kid")
        algorithm = header.get("alg")
        if (
            not isinstance(kid, str)
            or not kid
            or len(kid) > 256
            or algorithm not in _ALLOWED_ALGORITHMS
        ):
            raise InvalidAccessToken("bearer token uses an unsupported signing key")
        jwk = self._keys.get(kid)
        if jwk is not None and jwk.get("alg") not in (None, algorithm):
            raise InvalidAccessToken("token algorithm does not match issuer key")
        key = await self._get_key(kid)
        jwk = self._keys.get(kid)
        if jwk is None or jwk.get("alg") not in (None, algorithm):
            raise InvalidAccessToken("token algorithm does not match issuer key")
        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=[algorithm],
                audience=self.settings.audience,
                issuer=self.settings.issuer,
                leeway=30,
                options={"require": ["exp", "iat", "iss", "sub", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidAccessToken("bearer token could not be verified") from exc
        subject = claims.get("sub")
        issuer = claims.get("iss")
        if not isinstance(subject, str) or not subject or not isinstance(issuer, str):
            raise InvalidAccessToken("verified token has no stable subject")
        scopes: set[str] = set()
        scope_claim = claims.get("scope", "")
        if isinstance(scope_claim, str):
            scopes.update(part for part in scope_claim.split() if part)
        scp_claim = claims.get("scp", [])
        if isinstance(scp_claim, list):
            scopes.update(part for part in scp_claim if isinstance(part, str) and part)
        owner_id = hashlib.sha256(f"{issuer}\0{subject}".encode()).hexdigest()
        return Principal(owner_id, subject, frozenset(scopes), "oidc", issuer)


__all__ = [
    "AuthConfigurationError",
    "InvalidAccessToken",
    "OIDCSettings",
    "OIDCVerifier",
    "Principal",
]
