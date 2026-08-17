from tplinkcloud import TPLinkAuthError, TPLinkMFARequiredError

from app.token_blob import decode_session_token, encode_session_token

from .conftest import AUTH


async def test_login_returns_opaque_session_token(client):
    response = await client.post(
        "/api/v1/user/token",
        data={"username": "user@example.com", "password": "hunter2"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    blob = decode_session_token(body["access_token"])
    assert blob["kasa_token"] == "fake-kasa-token"
    assert blob["kasa_host"] == "https://test-wap.tplinkcloud.com"
    assert blob["term_id"]


async def test_login_rejects_bad_credentials(client, fleet):
    fleet["fleet"].login_error = TPLinkAuthError("Incorrect username or password")

    response = await client.post(
        "/api/v1/user/token",
        data={"username": "user@example.com", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_login_with_unexpected_cloud_host_maps_to_502(client, fleet):
    # Credentials were accepted, but TP-Link handed back a host outside the
    # allowlist: that's a cloud anomaly (502), not a bad client token (401).
    fleet["fleet"].login_host = "https://evil.example.com"

    response = await client.post(
        "/api/v1/user/token",
        data={"username": "user@example.com", "password": "hunter2"},
    )

    assert response.status_code == 502


async def test_login_reports_mfa_requirement(client, fleet):
    fleet["fleet"].login_error = TPLinkMFARequiredError(
        "MFA verification required", mfa_type="email", email="u***@example.com"
    )

    response = await client.post(
        "/api/v1/user/token",
        data={"username": "user@example.com", "password": "hunter2"},
    )

    assert response.status_code == 401
    assert response.json()["mfa_required"] is True


async def test_missing_bearer_is_rejected(client):
    response = await client.get("/api/v1/devices")

    assert response.status_code == 401


async def test_unrecognized_bearer_is_rejected(client):
    response = await client.get(
        "/api/v1/devices", headers={"Authorization": "Bearer not-a-session-token"}
    )

    assert response.status_code == 401


async def test_time_needs_no_auth(client):
    response = await client.get("/api/v1/time")

    assert response.status_code == 200
    assert response.json()["time"] > 0


async def test_sessions_are_isolated_per_token(client, fleet):
    first = await client.get("/api/v1/devices", headers=AUTH)
    assert first.status_code == 200
    assert len(first.json()["data"]) > 0

    # A different token builds a fresh session rather than reusing the cache
    fleet["fleet"].parents = []
    other_token = encode_session_token({"v": 1, "kasa_token": "other", "term_id": "t2"})
    second = await client.get("/api/v1/devices", headers={"Authorization": f"Bearer {other_token}"})
    assert second.status_code == 200
    assert second.json()["data"] == []

    # The original token still sees its cached session
    cached = await client.get("/api/v1/devices", headers=AUTH)
    assert len(cached.json()["data"]) > 0
