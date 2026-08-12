"""Fakes standing in for the tplinkcloud v5 library at the service boundary.

They duck-type exactly the surface TPLinkGateway/TPLinkSession and
TPLinkDeviceManagerPowerTools use; the library<->cloud HTTP contract is
covered by the library's own test suite.
"""

import asyncio
from types import SimpleNamespace


class FakeApi:
    def __init__(self, host="https://fake-regional.example"):
        self.host = host


class FakeDevice:
    def __init__(
        self,
        device_id,
        alias,
        model="HS110(US)",
        model_type="HS110",
        status=1,
        child_id=None,
        emeter=False,
        is_on=True,
        rssi=-48,
        children=None,
        cloud_type="kasa",
        sys_info_delay=0.0,
    ):
        self.device_id = device_id
        self.child_id = child_id
        self.device_info = SimpleNamespace(alias=alias, device_model=model, status=status)
        self.model_type = SimpleNamespace(name=model_type)
        self.cloud_type = cloud_type
        self._children = children or []
        self._on = is_on
        self._rssi = rssi
        self._emeter = emeter
        self._sys_info_delay = sys_info_delay
        self.power_calls = []

    def has_children(self):
        return bool(self._children)

    def has_emeter(self):
        return self._emeter

    def get_alias(self):
        return self.device_info.alias

    async def get_children_async(self):
        return self._children

    async def get_sys_info(self):
        if self._sys_info_delay:
            await asyncio.sleep(self._sys_info_delay)
        if self.device_info.status != 1:
            return None
        if self.child_id is not None:
            return {"id": self.child_id, "state": 1 if self._on else 0, "alias": self.get_alias()}
        info = SimpleNamespace(rssi=self._rssi)
        if self._children:
            info.children = [
                SimpleNamespace(id=c.child_id, state=1 if c._on else 0, alias=c.get_alias())
                for c in self._children
            ]
        else:
            info.relay_state = 1 if self._on else 0
        return info

    async def get_net_info(self):
        if self.device_info.status != 1:
            return None
        return SimpleNamespace(ssid="TestNet", rssi=self._rssi)

    async def is_on(self):
        if self.device_info.status != 1:
            return None
        return self._on

    async def power_on(self):
        self.power_calls.append("on")
        if self.device_info.status != 1:
            return None
        self._on = True
        return {"err_code": 0}

    async def power_off(self):
        self.power_calls.append("off")
        if self.device_info.status != 1:
            return None
        self._on = False
        return {"err_code": 0}

    async def get_power_usage_realtime(self):
        if self.device_info.status != 1:
            return None
        return SimpleNamespace(voltage_mv=120000, current_ma=500, power_mw=60000, total_wh=1234)

    async def get_power_usage_day(self, year, month):
        if self.device_info.status != 1:
            return []
        return [SimpleNamespace(year=year, month=month, day=1, energy_wh=100)]

    async def get_power_usage_month(self, year):
        if self.device_info.status != 1:
            return []
        return [SimpleNamespace(year=year, month=1, energy_wh=3000)]


class FakeManager:
    """Mirrors the tplinkcloud v5 TPLinkDeviceManager surface used by the service."""

    def __init__(self, fleet, username=None, password=None, term_id=None, **kwargs):
        self._fleet = fleet
        self._term_id = term_id
        self._kasa_api = FakeApi()
        self._tapo_api = None
        self._kasa_token = None
        self.init_kwargs = kwargs

        if username and password:
            if fleet.login_error is not None:
                raise fleet.login_error
            self._kasa_token = fleet.login_token

    def get_token(self):
        return self._kasa_token

    def get_tapo_token(self):
        return None

    def set_auth_token(self, token):
        self._kasa_token = token

    async def get_devices(self):
        if self._fleet.devices_error is not None:
            raise self._fleet.devices_error
        # Parents first, then children flattened in, mirroring the library
        devices = list(self._fleet.parents)
        for parent in self._fleet.parents:
            if parent.has_children() and parent.device_info.status == 1:
                devices.extend(await parent.get_children_async())
        return devices

    async def find_devices(self, device_names_like):
        return [
            d
            for d in await self.get_devices()
            if device_names_like.lower() in d.get_alias().lower()
        ]


class FakeFleet:
    """Holds the device fleet plus configurable login/list failure behavior."""

    def __init__(self, parents, login_token="fake-kasa-token"):
        self.parents = parents
        self.login_token = login_token
        self.login_error = None
        self.devices_error = None

    def factory(self, **kwargs):
        return FakeManager(self, **kwargs)
