import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.services.tplink_service import TPLinkGateway
from app.settings import Settings
from app.token_blob import encode_session_token

from .fakes import FakeDevice, FakeFleet

TEST_TOKEN = encode_session_token({"v": 1, "kasa_token": "fake-kasa-token", "term_id": "test-term"})
AUTH = {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture
def fleet():
    """A representative device fleet: emeter plug (on), plain plug (off),
    power strip with two outlets, and an offline emeter plug."""
    tv = FakeDevice(
        "dev-strip",
        "TV",
        model="HS300(US)",
        model_type="HS300CHILD",
        child_id="dev-strip00",
        emeter=True,
        is_on=True,
    )
    console = FakeDevice(
        "dev-strip",
        "Console",
        model="HS300(US)",
        model_type="HS300CHILD",
        child_id="dev-strip01",
        emeter=True,
        is_on=False,
    )
    devices = {
        "lamp": FakeDevice("dev-lamp", "Desk Lamp", model="HS110(US)", emeter=True, is_on=True),
        "fan": FakeDevice("dev-fan", "Fan", model="HS103(US)", model_type="HS103", is_on=False),
        "strip": FakeDevice(
            "dev-strip",
            "Media Strip",
            model="HS300(US)",
            model_type="HS300",
            children=[tv, console],
        ),
        "heater": FakeDevice(
            "dev-heater", "Heater", model="KP115(US)", model_type="KP115", status=0, emeter=True
        ),
        "tv": tv,
        "console": console,
    }
    fake_fleet = FakeFleet([devices["lamp"], devices["fan"], devices["strip"], devices["heater"]])
    return {"fleet": fake_fleet, **devices}


def build_app(fleet, **settings_overrides):
    settings_overrides.setdefault("cloud_timeout_seconds", 5)
    settings = Settings(**settings_overrides)
    application = create_app(settings)
    application.state.gateway = TPLinkGateway(settings, manager_factory=fleet["fleet"].factory)
    return application


@pytest.fixture
def app(fleet):
    return build_app(fleet)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
