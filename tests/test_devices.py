from .conftest import AUTH


def by_key(devices):
    return {(d["device_id"], d["child_id"]): d for d in devices}


async def test_list_flattens_strip_children(client):
    response = await client.get("/api/v1/devices", headers=AUTH)

    assert response.status_code == 200
    devices = by_key(response.json()["data"])
    # 4 physical devices + 2 strip outlets
    assert len(devices) == 6

    tv = devices[("dev-strip", "dev-strip00")]
    assert tv["alias"] == "TV"
    assert tv["is_on"] is True
    assert tv["model"] == "HS300(US)"
    assert tv["has_emeter"] is True

    console = devices[("dev-strip", "dev-strip01")]
    assert console["is_on"] is False

    # The strip itself has no single on/off state
    strip = devices[("dev-strip", None)]
    assert strip["is_on"] is None
    assert strip["is_online"] is True

    lamp = devices[("dev-lamp", None)]
    assert lamp["is_on"] is True
    assert lamp["rssi"] == -48


async def test_list_marks_offline_devices(client):
    response = await client.get("/api/v1/devices", headers=AUTH)

    heater = by_key(response.json()["data"])[("dev-heater", None)]
    assert heater["is_online"] is False
    assert heater["is_on"] is None


async def test_list_filters(client):
    by_name = await client.get("/api/v1/devices", params={"name": "fan"}, headers=AUTH)
    assert [d["alias"] for d in by_name.json()["data"]] == ["Fan"]

    by_model = await client.get("/api/v1/devices", params={"model": "hs300"}, headers=AUTH)
    assert len(by_model.json()["data"]) == 3  # strip + 2 outlets

    off = await client.get("/api/v1/devices", params={"state": "off"}, headers=AUTH)
    assert sorted(d["alias"] for d in off.json()["data"]) == ["Console", "Fan"]

    offline = await client.get("/api/v1/devices", params={"state": "offline"}, headers=AUTH)
    assert [d["alias"] for d in offline.json()["data"]] == ["Heater"]


async def test_device_detail(client):
    response = await client.get("/api/v1/devices/dev-lamp", headers=AUTH)

    assert response.status_code == 200
    detail = response.json()["data"]
    assert detail["alias"] == "Desk Lamp"
    assert detail["is_on"] is True
    assert detail["sys_info"]["relay_state"] == 1
    assert detail["net_info"]["ssid"] == "TestNet"


async def test_device_detail_for_strip_child(client):
    response = await client.get(
        "/api/v1/devices/dev-strip", params={"child_id": "dev-strip01"}, headers=AUTH
    )

    detail = response.json()["data"]
    assert detail["alias"] == "Console"
    assert detail["is_on"] is False
    assert detail["sys_info"]["state"] == 0


async def test_unknown_device_is_404(client):
    response = await client.get("/api/v1/devices/nope", headers=AUTH)

    assert response.status_code == 404


async def test_system_info(client):
    response = await client.get("/api/v1/devices/dev-lamp/systeminfo", headers=AUTH)

    assert response.status_code == 200
    assert response.json()["data"]["relay_state"] == 1


async def test_power_on(client, fleet):
    response = await client.post(
        "/api/v1/devices/dev-fan/power", json={"action": "on"}, headers=AUTH
    )

    assert response.status_code == 200
    assert response.json() == {"device_id": "dev-fan", "child_id": None, "is_on": True}
    assert fleet["fan"].power_calls == ["on"]


async def test_power_toggle(client, fleet):
    response = await client.post(
        "/api/v1/devices/dev-lamp/power", json={"action": "toggle"}, headers=AUTH
    )

    assert response.json()["is_on"] is False
    assert fleet["lamp"].power_calls == ["off"]


async def test_power_on_strip_child(client, fleet):
    response = await client.post(
        "/api/v1/devices/dev-strip/power",
        params={"child_id": "dev-strip01"},
        json={"action": "on"},
        headers=AUTH,
    )

    assert response.json() == {"device_id": "dev-strip", "child_id": "dev-strip01", "is_on": True}
    assert fleet["console"].power_calls == ["on"]
    # The parent strip itself was not touched
    assert fleet["strip"].power_calls == []


async def test_power_on_offline_device_conflicts(client, fleet):
    response = await client.post(
        "/api/v1/devices/dev-heater/power", json={"action": "on"}, headers=AUTH
    )

    assert response.status_code == 409
    assert fleet["heater"].power_calls == []


async def test_power_rejects_bad_action(client):
    response = await client.post(
        "/api/v1/devices/dev-lamp/power", json={"action": "blink"}, headers=AUTH
    )

    assert response.status_code == 422


def test_decode_alias():
    from app.services.tplink_service import decode_alias

    # Some devices (e.g. DL-series doorbells) report their alias
    # base64-encoded via the cloud list
    assert decode_alias("R2FyYWdlIExpZ2h0") == "Garage Light"
    # Ordinary aliases pass through untouched
    assert decode_alias("Desk Lamp") == "Desk Lamp"
    assert decode_alias("Duster") == "Duster"
    assert decode_alias("Desk Plug 1") == "Desk Plug 1"
    assert decode_alias("") == ""
