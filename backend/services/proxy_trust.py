"""Proof that a request comes from our own Next.js server, so its X-Forwarded-For can be believed.

Both servers share JWT_SECRET_KEY (the same environment). The proxy sends an HMAC of a fixed
label under that secret in X-Nora-Proxy; nobody without the secret can forge it. The Node side is
lib/server-session.ts (proxyProof). Without a configured secret there is no proof, and the peer
address is used.
"""

import hashlib
import hmac

from config import settings

PROXY_HEADER = "x-nora-proxy"
LABEL = b"nora-medlink-proxy-v1"


def expected_proof() -> str | None:
    if not settings.jwt_secret:
        return None
    return hmac.new(settings.jwt_secret.encode(), LABEL, hashlib.sha256).hexdigest()


def valid_proxy_proof(value: str | None) -> bool:
    expected = expected_proof()
    return bool(expected and value and hmac.compare_digest(value, expected))
