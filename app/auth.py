"""Small, dependency-free password hashing and signed-cookie session helpers."""
import base64
import hashlib
import hmac
import json
import secrets
import time

from .config import settings

PASSWORD_ITERATIONS = 310_000
SESSION_TTL_SECONDS = 60 * 60 * 12

# Local development remains usable without another setup step. Configure AUTH_SECRET in
# .env for stable sessions across restarts and deployments.
_runtime_secret = settings.auth_secret.encode() if settings.auth_secret else secrets.token_bytes(32)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(iterations))
        return hmac.compare_digest(digest, _unb64(expected))
    except (ValueError, TypeError):
        return False


def issue_session(user_id: int, session_version: int) -> str:
    payload = _b64(json.dumps({"uid": user_id, "ver": session_version,
                               "exp": int(time.time()) + SESSION_TTL_SECONDS},
                              separators=(",", ":")).encode())
    signature = _b64(hmac.new(_runtime_secret, payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def read_session(token: str | None) -> dict | None:
    if not token or "." not in token:
        return None
    payload, signature = token.rsplit(".", 1)
    expected = hmac.new(_runtime_secret, payload.encode(), hashlib.sha256).digest()
    try:
        if not hmac.compare_digest(expected, _unb64(signature)):
            return None
        body = json.loads(_unb64(payload))
        if int(body["exp"]) < int(time.time()):
            return None
        return body
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
