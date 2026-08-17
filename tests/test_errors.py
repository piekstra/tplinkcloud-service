from httpx import ASGITransport, AsyncClient
from tplinkcloud import TPLinkCloudError, TPLinkTokenExpiredError

from .conftest import AUTH, build_app
from .fakes import FakeDevice, FakeFleet


async def request_devices(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/api/v1/devices", headers=AUTH)


async def test_expired_token_maps_to_401(fleet):
    fleet["fleet"].devices_error = TPLinkTokenExpiredError("Token expired")

    response = await request_devices(build_app(fleet))

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert "Token expired" in response.json()["detail"]


async def test_cloud_error_maps_to_502(fleet):
    fleet["fleet"].devices_error = TPLinkCloudError("Something else broke", error_code=-99999)

    response = await request_devices(build_app(fleet))

    assert response.status_code == 502


async def test_unreachable_cloud_maps_to_502(fleet):
    fleet["fleet"].devices_error = ConnectionError("boom")

    response = await request_devices(build_app(fleet))

    assert response.status_code == 502


async def test_slow_cloud_maps_to_504():
    slow = FakeDevice("dev-slow", "Slow Plug", sys_info_delay=0.2)
    fleet = {"fleet": FakeFleet([slow])}

    response = await request_devices(build_app(fleet, cloud_timeout_seconds=0.05))

    assert response.status_code == 504
