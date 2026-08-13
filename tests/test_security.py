"""Security-focused tests: SSRF guard on the session token's regional host,
and the library-contract guard that keeps the private-attribute coupling honest.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.token_blob import encode_session_token

from .conftest import build_app


async def _get_devices(app, token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/api/v1/devices", headers={"Authorization": f"Bearer {token}"})


@pytest.mark.parametrize(
    "bad_host",
    [
        "http://169.254.169.254",  # cloud metadata endpoint
        "http://localhost:8000",  # internal service
        "https://evil.example.com",  # attacker collector
        "https://tplinkcloud.com.evil.com",  # suffix-spoof
        "http://test-wap.tplinkcloud.com",  # right host, wrong scheme
    ],
)
async def test_forged_regional_host_is_rejected(fleet, bad_host):
    # A forged, unsigned token pointing the regional API host at an
    # attacker-chosen destination must never be honored (SSRF / cred exfil).
    token = encode_session_token(
        {"v": 1, "kasa_token": "stolen-or-fake", "kasa_host": bad_host, "term_id": "t"}
    )

    response = await _get_devices(build_app(fleet), token)

    assert response.status_code == 401


def test_host_allowlist_boundary_is_structural_without_leading_dot():
    # An operator may list a bare domain (no leading dot); the label boundary
    # must still hold so a lookalike host is not silently allowed.
    from app.services.tplink_service import _host_allowed

    allow = ["tplinkcloud.com"]
    assert _host_allowed("https://wap.tplinkcloud.com", allow) is True
    assert _host_allowed("https://tplinkcloud.com", allow) is True
    assert _host_allowed("https://eviltplinkcloud.com", allow) is False
    assert _host_allowed("https://tplinkcloud.com.evil.com", allow) is False
    assert _host_allowed("http://wap.tplinkcloud.com", allow) is False  # non-https


async def test_allowlisted_regional_host_is_accepted(fleet):
    token = encode_session_token(
        {
            "v": 1,
            "kasa_token": "fake-kasa-token",
            "kasa_host": "https://use1-wap.tplinkcloud.com",
            "term_id": "t",
        }
    )

    response = await _get_devices(build_app(fleet), token)

    assert response.status_code == 200


def test_library_manager_exposes_the_internals_we_depend_on():
    """Session restore reaches into a few tplinkcloud internals (no public
    accessors yet). Pin them so a library bump that renames one fails here
    rather than in production. Constructing without credentials makes no
    network calls."""
    from tplinkcloud import TPLinkDeviceManager

    manager = TPLinkDeviceManager(prefetch=False, cache_devices=True, include_tapo=True)

    assert hasattr(manager, "_kasa_api")
    assert hasattr(manager._kasa_api, "host")
    assert hasattr(manager, "_tapo_api")
    assert hasattr(manager._tapo_api, "host")
    assert hasattr(manager, "_tapo_token")
    # Public surface the restore path also relies on
    assert callable(manager.set_auth_token)
    assert callable(manager.get_token)
    assert callable(manager.get_tapo_token)
