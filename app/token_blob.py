"""Opaque session token minted by this service.

TP-Link's v2 cloud auth produces more than a single token: a Kasa token, an
optional Tapo token, the per-account regional API hosts, and the terminal id
the tokens were minted under. To stay stateless, the whole set is packed into
one opaque bearer token (base64url JSON) that the client stores and replays.
"""

import base64
import binascii
import json

from app.errors import InvalidServiceTokenError


def encode_session_token(payload: dict) -> str:
    compact = {key: value for key, value in payload.items() if value is not None}
    raw = json.dumps(compact, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_session_token(token: str) -> dict:
    try:
        padded = token + "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise InvalidServiceTokenError() from exc
    if not isinstance(payload, dict) or "kasa_token" not in payload:
        raise InvalidServiceTokenError()
    return payload
