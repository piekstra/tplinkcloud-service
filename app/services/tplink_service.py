import asyncio
import logging
import uuid
from decimal import Decimal
from typing import Literal

from tplinkcloud import (
    TPLinkCloudError,
    TPLinkDeviceManager,
    TPLinkDeviceManagerPowerTools,
)

from app.cache import SessionCache
from app.errors import DeviceNotFoundError, DeviceOfflineError
from app.models import DeviceSummary
from app.settings import Settings
from app.token_blob import decode_session_token, encode_session_token

logger = logging.getLogger(__name__)

PowerAction = Literal["on", "off", "toggle"]


def jsonify(data):
    """Recursively convert tplinkcloud's plain classes into JSON-safe values."""
    if type(data) is list:
        return [jsonify(item) for item in data]
    elif type(data) is dict:
        return {key: jsonify(value) for key, value in data.items()}
    elif type(data) in [int, float, str, bool]:
        return data
    elif type(data) is Decimal:
        return str(data)
    # classes
    elif hasattr(data, "__dict__"):
        return jsonify(vars(data))
    # Enums
    elif hasattr(data, "name"):
        return data.name

    return None


def _info_value(sys_info, key):
    """Read a field from a sys_info that may be a typed object (Kasa) or a raw dict (Tapo)."""
    if isinstance(sys_info, dict):
        return sys_info.get(key)
    return getattr(sys_info, key, None)


class TPLinkGateway:
    """Entry point for all TP-Link cloud access: login plus per-token cached sessions."""

    def __init__(self, settings: Settings, manager_factory=None):
        self._settings = settings
        self._manager_factory = manager_factory or TPLinkDeviceManager
        self._sessions = SessionCache(
            maxsize=settings.device_cache_max_sessions,
            ttl=settings.device_cache_ttl,
        )

    def _manager_kwargs(self) -> dict:
        kwargs = {"prefetch": False, "cache_devices": True, "verbose": False}
        if self._settings.tplink_cloud_api_host:
            kwargs["tplink_cloud_api_host"] = self._settings.tplink_cloud_api_host
        return kwargs

    async def login(self, username: str, password: str, mfa_code: str | None = None) -> str | None:
        """Authenticate against the TP-Link clouds and mint an opaque session token.

        Raises the library's typed errors (TPLinkAuthError, TPLinkMFARequiredError,
        TPLinkCloudError) which the exception handlers map onto HTTP statuses.
        """
        # Tokens are bound to the terminal UUID they were minted under, so a
        # stable one is generated per login and carried inside the session token.
        term_id = str(uuid.uuid4())

        def build() -> TPLinkDeviceManager:
            kwargs = self._manager_kwargs() | {"term_id": term_id}
            if mfa_code:
                kwargs["mfa_callback"] = lambda mfa_type, email: mfa_code
            # Construction with credentials performs the (blocking) cloud logins
            return self._manager_factory(username=username, password=password, **kwargs)

        try:
            manager = await asyncio.to_thread(build)
        except ValueError:
            # The library raises ValueError for missing credentials
            return None

        kasa_token = manager.get_token()
        if not kasa_token:
            return None

        tapo_api = getattr(manager, "_tapo_api", None)
        return encode_session_token(
            {
                "v": 1,
                "term_id": term_id,
                "kasa_token": kasa_token,
                # Login discovers the account's regional API host; data calls
                # must go to the same host. There is no public getter.
                "kasa_host": manager._kasa_api.host,
                "tapo_token": manager.get_tapo_token(),
                "tapo_host": tapo_api.host if tapo_api else None,
            }
        )

    async def session(self, token: str) -> "TPLinkSession":
        return await self._sessions.get_or_create(token, lambda: self._create_session(token))

    async def _create_session(self, token: str) -> "TPLinkSession":
        blob = decode_session_token(token)

        # Constructing without credentials performs no network calls
        manager = self._manager_factory(
            **self._manager_kwargs(),
            term_id=blob.get("term_id"),
            include_tapo=bool(blob.get("tapo_token")),
        )
        manager.set_auth_token(blob["kasa_token"])
        if blob.get("kasa_host"):
            # Restore the regional host discovered at login (no public setter)
            manager._kasa_api.host = blob["kasa_host"]
        if blob.get("tapo_token") and getattr(manager, "_tapo_api", None):
            # The library has no public setter for the Tapo token pair
            manager._tapo_token = blob["tapo_token"]
            if blob.get("tapo_host"):
                manager._tapo_api.host = blob["tapo_host"]

        session = TPLinkSession(manager, self._settings)
        await session.load_devices()
        return session


class TPLinkSession:
    """A per-token view of the account's devices, valid for one cache TTL."""

    def __init__(self, manager: TPLinkDeviceManager, settings: Settings):
        self._manager = manager
        self._settings = settings
        self._power_tools = TPLinkDeviceManagerPowerTools(manager)
        self._devices = []

    async def load_devices(self):
        # get_devices() has an async signature but fetches the cloud device
        # list with blocking `requests` internally; run the whole call on a
        # worker thread with its own event loop. Auth failures surface as the
        # library's typed errors (e.g. TPLinkTokenExpiredError -> 401).
        try:
            async with asyncio.timeout(self._settings.cloud_timeout_seconds):
                self._devices = await asyncio.to_thread(asyncio.run, self._manager.get_devices())
        except (TPLinkCloudError, TimeoutError):
            raise
        except Exception as exc:
            raise TPLinkCloudError(f"TP-Link cloud is unreachable: {exc}") from exc
        return self._devices

    def _parents(self):
        return {d.device_id: d for d in self._devices if d.child_id is None}

    def _find_device(self, device_id: str, child_id: str | None = None):
        for device in self._devices:
            if device.device_id == device_id and device.child_id == child_id:
                return device
        raise DeviceNotFoundError(device_id, child_id)

    async def device_summaries(
        self,
        name: str | None = None,
        model: str | None = None,
        state: Literal["on", "off", "offline"] | None = None,
    ) -> list[DeviceSummary]:
        parents = self._parents()
        online_ids = [
            device_id for device_id, device in parents.items() if device.device_info.status == 1
        ]

        # One sys_info call per online physical device; children derive their
        # state from the parent's response.
        async with asyncio.timeout(self._settings.cloud_timeout_seconds):
            results = await asyncio.gather(
                *(parents[device_id].get_sys_info() for device_id in online_ids),
                return_exceptions=True,
            )
        sys_infos = {}
        for device_id, result in zip(online_ids, results, strict=True):
            if isinstance(result, Exception):
                logger.warning("sys_info fetch failed for device %s: %s", device_id, result)
            else:
                sys_infos[device_id] = result

        summaries = [self._summarize(device, parents, sys_infos) for device in self._devices]

        if name is not None:
            summaries = [s for s in summaries if name.lower() in s.alias.lower()]
        if model is not None:
            summaries = [s for s in summaries if model.lower() in s.model.lower()]
        if state == "on":
            summaries = [s for s in summaries if s.is_on is True]
        elif state == "off":
            summaries = [s for s in summaries if s.is_on is False]
        elif state == "offline":
            summaries = [s for s in summaries if not s.is_online]

        return summaries

    def _summarize(self, device, parents, sys_infos) -> DeviceSummary:
        parent = parents.get(device.device_id)
        is_online = bool(parent and parent.device_info.status == 1)
        sys_info = sys_infos.get(device.device_id)

        is_on = None
        rssi = None
        if sys_info is not None:
            rssi = _info_value(sys_info, "rssi")
            if device.child_id is not None:
                children = _info_value(sys_info, "children") or []
                child = next((c for c in children if _info_value(c, "id") == device.child_id), None)
                if child is not None:
                    is_on = _info_value(child, "state") == 1
            elif device.has_children():
                # A strip's outlets switch individually; the parent has no single on/off
                is_on = None
            else:
                relay_state = _info_value(sys_info, "relay_state")
                is_on = relay_state == 1 if relay_state is not None else None

        return DeviceSummary(
            device_id=device.device_id,
            child_id=device.child_id,
            alias=device.get_alias(),
            model=parent.device_info.device_model if parent else "",
            device_type=device.model_type.name,
            cloud=getattr(device, "cloud_type", "kasa") or "kasa",
            is_online=is_online,
            is_on=is_on,
            has_emeter=device.has_emeter(),
            rssi=rssi,
        )

    async def device_detail(self, device_id: str, child_id: str | None = None) -> dict:
        device = self._find_device(device_id, child_id)
        parent = self._parents().get(device_id)
        is_online = bool(parent and parent.device_info.status == 1)

        sys_info = None
        net_info = None
        if is_online:
            async with asyncio.timeout(self._settings.cloud_timeout_seconds):
                sys_info, net_info = await asyncio.gather(
                    device.get_sys_info(), device.get_net_info(), return_exceptions=True
                )
            if isinstance(sys_info, Exception):
                logger.warning("sys_info fetch failed for %s: %s", device_id, sys_info)
                sys_info = None
            if isinstance(net_info, Exception):
                net_info = None

        raw_sys_info = jsonify(sys_info)
        is_on = None
        if raw_sys_info:
            if device.child_id is not None:
                is_on = raw_sys_info.get("state") == 1
            elif not device.has_children():
                relay_state = raw_sys_info.get("relay_state")
                is_on = relay_state == 1 if relay_state is not None else None

        return {
            "device_id": device.device_id,
            "child_id": device.child_id,
            "alias": device.get_alias(),
            "model": parent.device_info.device_model if parent else "",
            "device_type": device.model_type.name,
            "cloud": getattr(device, "cloud_type", "kasa") or "kasa",
            "is_online": is_online,
            "is_on": is_on,
            "has_emeter": device.has_emeter(),
            "rssi": raw_sys_info.get("rssi") if raw_sys_info else None,
            "sys_info": raw_sys_info,
            "net_info": jsonify(net_info),
        }

    async def device_sys_info(self, device_id: str, child_id: str | None = None):
        device = self._find_device(device_id, child_id)
        async with asyncio.timeout(self._settings.cloud_timeout_seconds):
            return jsonify(await device.get_sys_info())

    async def set_power(
        self, device_id: str, action: PowerAction, child_id: str | None = None
    ) -> dict:
        device = self._find_device(device_id, child_id)
        parent = self._parents().get(device_id)
        if parent is None or parent.device_info.status != 1:
            raise DeviceOfflineError(device_id)

        async with asyncio.timeout(self._settings.cloud_timeout_seconds):
            if action == "toggle":
                currently_on = await device.is_on()
                if currently_on is None:
                    raise DeviceOfflineError(device_id)
                action = "off" if currently_on else "on"

            result = await (device.power_on() if action == "on" else device.power_off())
            if result is None:
                # The pass-through returned nothing: the device dropped offline
                raise DeviceOfflineError(device_id)

            return {
                "device_id": device_id,
                "child_id": child_id,
                "is_on": await device.is_on(),
            }

    async def power_usage_realtime(self, devices_like: str | None = None):
        async with asyncio.timeout(self._settings.cloud_timeout_seconds):
            usage = await self._power_tools.get_devices_power_usage_realtime(devices_like)
        return jsonify(usage)

    async def power_usage_day(self, devices_like: str | None = None):
        async with asyncio.timeout(self._settings.cloud_timeout_seconds):
            usage = await self._power_tools.get_devices_power_usage_day(devices_like)
        return jsonify(usage)

    async def power_usage_month(self, devices_like: str | None = None):
        async with asyncio.timeout(self._settings.cloud_timeout_seconds):
            usage = await self._power_tools.get_devices_power_usage_month(devices_like)
        return jsonify(usage)
