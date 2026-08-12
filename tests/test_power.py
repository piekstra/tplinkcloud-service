from .conftest import AUTH


async def test_current_power_covers_all_emeter_devices(client):
    response = await client.get("/api/v1/power/devices/current", headers=AUTH)

    assert response.status_code == 200
    data = response.json()["data"]
    # lamp + 2 strip outlets + offline heater (with null data)
    assert sorted(d["name"] for d in data) == ["Console", "Desk Lamp", "Heater", "TV"]

    lamp = next(d for d in data if d["name"] == "Desk Lamp")
    assert lamp["device_id"] == "dev-lamp"
    assert lamp["data"] == {
        "voltage_mv": 120000,
        "current_ma": 500,
        "power_mw": 60000,
        "total_wh": 1234,
    }

    heater = next(d for d in data if d["name"] == "Heater")
    assert heater["data"] is None


async def test_current_power_named_filter(client):
    response = await client.get(
        "/api/v1/power/devices/current", params={"named": "desk"}, headers=AUTH
    )

    assert [d["name"] for d in response.json()["data"]] == ["Desk Lamp"]


async def test_strip_children_carry_child_id(client):
    response = await client.get("/api/v1/power/devices/current", headers=AUTH)

    tv = next(d for d in response.json()["data"] if d["name"] == "TV")
    assert tv["device_id"] == "dev-strip"
    assert tv["child_id"] == "dev-strip00"


async def test_day_power_shape(client):
    response = await client.get("/api/v1/power/devices/day", headers=AUTH)

    assert response.status_code == 200
    lamp = next(d for d in response.json()["data"] if d["name"] == "Desk Lamp")
    sample = lamp["data"][0]
    assert set(sample) == {"year", "month", "day", "energy_wh"}


async def test_month_power_shape(client):
    response = await client.get("/api/v1/power/devices/month", headers=AUTH)

    assert response.status_code == 200
    lamp = next(d for d in response.json()["data"] if d["name"] == "Desk Lamp")
    sample = lamp["data"][0]
    assert set(sample) == {"year", "month", "energy_wh"}
