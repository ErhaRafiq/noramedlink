"""Rate-limit keys and the per-account login limit (rate_limit.py)."""

import secrets

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import rate_limit
from auth import create_access_token
from rate_limit import client_ip, enforce_account_limit, ip_key, user_or_ip_key


def make_request(peer: str = "203.0.113.9", headers: dict[str, str] | None = None) -> Request:
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": raw_headers, "client": (peer, 5000)})


def test_direct_client_uses_its_own_address():
    assert client_ip(make_request("203.0.113.9")) == "203.0.113.9"


def test_forwarded_header_is_ignored_from_untrusted_peers():
    request = make_request("203.0.113.9", {"X-Forwarded-For": "198.51.100.1"})
    assert client_ip(request) == "203.0.113.9"


def test_forwarded_header_is_used_from_the_trusted_proxy():
    request = make_request("127.0.0.1", {"X-Forwarded-For": "198.51.100.1, 127.0.0.1"})
    assert client_ip(request) == "198.51.100.1"


def test_signed_in_requests_are_counted_per_user():
    token = create_access_token("42")
    request = make_request(headers={"Authorization": f"Bearer {token}"})
    assert user_or_ip_key(request) == "user:42"


@pytest.mark.parametrize("authorization", ["Bearer not-a-jwt", "Basic abc", ""])
def test_invalid_or_missing_tokens_fall_back_to_the_ip(authorization):
    request = make_request("203.0.113.9", {"Authorization": authorization} if authorization else {})
    assert user_or_ip_key(request) == ip_key(request) == "ip:203.0.113.9"


def test_a_forged_token_does_not_pick_the_user():
    token = create_access_token("42")
    header, _payload, signature = token.split(".")
    forged = f"{header}.eyJzdWIiOiIxIn0.{signature}"  # payload {"sub":"1"}, original signature
    assert user_or_ip_key(make_request(headers={"Authorization": f"Bearer {forged}"})).startswith("ip:")


@pytest.mark.skipif(not rate_limit.RATE_LIMIT_ENABLED, reason="rate limiting is turned off in this environment")
def test_account_limit_allows_the_limit_then_returns_429():
    email = f"unit-{secrets.token_hex(6)}@example.com"
    for _ in range(5):
        enforce_account_limit("login-test", email, "5/minute")
    with pytest.raises(HTTPException) as caught:
        enforce_account_limit("login-test", email.upper(), "5/minute")  # same account, any case
    assert caught.value.status_code == 429
    assert int(caught.value.headers["Retry-After"]) >= 1
    # Another account is unaffected.
    enforce_account_limit("login-test", f"other-{email}", "5/minute")
