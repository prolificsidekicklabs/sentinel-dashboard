from __future__ import annotations

import asyncio
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from sentinel_core.auth import (
    AuthConfigurationError,
    InvalidAccessToken,
    OIDCSettings,
    OIDCVerifier,
)

ISSUER = "https://identity.example.test/"
AUDIENCE = "sentinel-api"
JWKS_URL = "https://identity.example.test/.well-known/jwks.json"


@pytest.fixture
def signing_material() -> tuple[object, dict[str, object]]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key(), as_dict=True)
    public_jwk.update({"kid": "test-key-1", "alg": "RS256", "use": "sig"})
    return private, public_jwk


def _token(private: object, **overrides: object) -> str:
    now = int(time.time())
    claims: dict[str, object] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "user-123",
        "iat": now,
        "exp": now + 300,
        "scope": "credentials:read paper:trade",
        "tenant_id": "tenant-a",
    }
    claims.update(overrides)
    return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "test-key-1"})


def test_oidc_verifies_signature_claims_and_user_scopes(
    signing_material: tuple[object, dict[str, object]],
) -> None:
    private, jwk = signing_material

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL(JWKS_URL)
        return httpx.Response(200, json={"keys": [jwk]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    verifier = OIDCVerifier(
        OIDCSettings(ISSUER, AUDIENCE, JWKS_URL),
        http_client=client,
    )
    principal = asyncio.run(verifier.verify(_token(private)))
    asyncio.run(client.aclose())

    assert principal.subject == "user-123"
    assert principal.auth_method == "oidc"
    assert principal.issuer == ISSUER
    assert principal.has_scope("paper:trade")
    assert principal.owner_id != principal.subject


def test_oidc_fails_closed_on_wrong_audience_issuer_or_expiry(
    signing_material: tuple[object, dict[str, object]],
) -> None:
    private, jwk = signing_material

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"keys": [jwk]})

    async def reject(token: str) -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(InvalidAccessToken):
                await OIDCVerifier(
                    OIDCSettings(ISSUER, AUDIENCE, JWKS_URL), http_client=client
                ).verify(token)
        finally:
            await client.aclose()

    asyncio.run(reject(_token(private, aud="other-api")))
    asyncio.run(reject(_token(private, iss="https://attacker.example.test/")))
    asyncio.run(reject(_token(private, exp=int(time.time()) - 60)))


def test_oidc_settings_require_complete_https_configuration() -> None:
    with pytest.raises(AuthConfigurationError):
        OIDCSettings.from_environment({"SENTINEL_OIDC_ISSUER": "https://issuer.test"})
    with pytest.raises(AuthConfigurationError):
        OIDCSettings.from_environment(
            {
                "SENTINEL_OIDC_ISSUER": "http://issuer.test",
                "SENTINEL_OIDC_AUDIENCE": "sentinel",
                "SENTINEL_OIDC_JWKS_URL": "https://issuer.test/jwks",
            }
        )


def test_unknown_signing_key_refresh_is_rate_limited(
    signing_material: tuple[object, dict[str, object]],
) -> None:
    _, jwk = signing_material
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json={"keys": [jwk]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    verifier = OIDCVerifier(
        OIDCSettings(ISSUER, AUDIENCE, JWKS_URL),
        http_client=client,
        clock=lambda: 1_000,
    )

    async def reject_unknown_key_twice() -> None:
        try:
            for _ in range(2):
                with pytest.raises(InvalidAccessToken):
                    await verifier._get_key("attacker-selected-kid")
        finally:
            await client.aclose()

    asyncio.run(reject_unknown_key_twice())
    assert requests == 1
