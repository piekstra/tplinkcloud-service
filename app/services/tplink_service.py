import asyncio
import base64
import logging
import re
import uuid
from decimal import Decimal
from typing import Literal
from urllib.parse import urlparse

from tplinkcloud import (
    TPLinkCloudError,
    TPLinkDeviceManager,
    TPLinkDeviceManagerPowerTools,
)

from app.cache import SessionCache
from app.errors import DeviceNotFoundError, DeviceOfflineError, InvalidServiceTokenError
from app.models import DeviceDetail, DeviceSummary
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


def _host_allowed(host: str, allowed_suffixes) -> bool:
    """The regional API host from a session token becomes the outbound request
    destination; allow only https TP-Link domains so a tampered token can't
    point credentialed requests at an attacker-chosen host (SSRF)."""
    parsed = urlparse(host)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    hostname = parsed.hostname.lower()
    for suffix in allowed_suffixes:
        # Normalize so "example.com" and ".example.com" are equivalent and the
        # label boundary is structural — an operator who lists a bare domain
        # must not accidentally allow "evilexample.com".
        entry = suffix.lower().lstrip(".")
        if hostname == entry or hostname.endswith("." + entry):
            return True
    return False


_BASE64_ALIAS_RE = re.compile(r"^[A-Za-z0-9+/]{8,}={0,2}$")


def decode_alias(alias):
    """Some devices (e.g. the DL110 doorbell) report base64-encoded aliases
    through the cloud list; the official app decodes them. Only rewrites
    strings that strictly decode to printable text."""
    if not alias or len(alias) % 4 != 0 or not _BASE64_ALIAS_RE.match(alias):
        return alias
    try:
        decoded = base64.b64decode(alias, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return alias
    return decoded if decoded and decoded.isprintable() else alias


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

        # Login discovers the account's regional API host; data calls must go to
        # the same host, so it travels in the token. Validate it here too — if
        # TP-Link ever returns a host outside the allowlist, fail loudly at mint
        # rather than minting a token that restore will reject.
        kasa_host = self._validated_host(manager._kasa_api.host, minting=True)
        tapo_api = getattr(manager, "_tapo_api", None)
        tapo_host = self._validated_host(tapo_api.host, minting=True) if tapo_api else None
        return encode_session_token(
            {
                "v": 1,
                "term_id": term_id,
                "kasa_token": kasa_token,
                "kasa_host": kasa_host,
                "tapo_token": manager.get_tapo_token(),
                "tapo_host": tapo_host,
            }
        )

    def _validated_host(self, host: str | None, *, minting: bool = False) -> str | None:
        if host is None:
            return None
        if not _host_allowed(host, self._settings.allowed_cloud_host_suffixes):
            if minting:
                # We just authenticated the user; a bad host is TP-Link returning
                # something unexpected, not a bad client token. 502, not 401.
                raise TPLinkCloudError("TP-Link returned an API host outside the allowed domains")
            raise InvalidServiceTokenError()
        return host

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
            # Restore the regional host discovered at login. Re-validate: the
            # token is client-supplied and unsigned, so an allowlisted host is
            # what keeps this from being an SSRF sink (no public setter, hence
            # the private attribute). See _validated_host / _host_allowed.
            manager._kasa_api.host = self._validated_host(blob["kasa_host"])
        if blob.get("tapo_token") and getattr(manager, "_tapo_api", None):
            # The library has no public setter for the Tapo token pair
            manager._tapo_token = blob["tapo_token"]
            if blob.get("tapo_host"):
                manager._tapo_api.host = self._validated_host(blob["tapo_host"])

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
        # Offloading seam: the library's device *commands* (sys_info, power,
        # emeter — see device_summaries/device_detail/set_power) use aiohttp and
        # are awaited directly. Only login and this device-list fetch use blocking
        # `requests`, so only they are pushed to a worker thread. get_devices()
        # has an async signature but does the blocking fetch internally, hence
        # to_thread(asyncio.run, ...). Auth failures surface as the library's
        # typed errors (e.g. TPLinkTokenExpiredError -> 401).
        #
        # Note: asyncio.timeout bounds how long we WAIT for the response, not the
        # worker thread — to_thread can't be cancelled. The thread itself is
        # bounded instead by the library's own per-request socket timeout (~15s
        # in tplink-cloud-api's requests calls), so a slow cloud frees the pool
        # slot on that timescale rather than hanging indefinitely.
        try:
            async with asyncio.timeout(self._settings.cloud_timeout_seconds):
                self._devices = await asyncio.to_thread(asyncio.run, self._manager.get_devices())
        except (TPLinkCloudError, TimeoutError):
            raise
        except (ConnectionError, OSError) as exc:
            # A genuine transport failure reaching the cloud -> 502
            raise TPLinkCloudError("Unable to reach the TP-Link cloud") from exc
        except Exception:
            # Anything else is almost certainly a bug in this service (e.g. the
            # library changed a private attribute we depend on). Surface it as a
            # 502 but log the real traceback rather than blaming the vendor
            # silently, and don't echo internal detail to the client.
            logger.exception("Unexpected error fetching device list")
            raise TPLinkCloudError("Unable to load devices") from None
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
                else:
                    # device_detail fetches the outlet's own sys_info, which
                    # carries `state` directly instead of a parent children list
                    state = _info_value(sys_info, "state")
                    if state is not None:
                        is_on = state == 1
            elif device.has_children():
                # A strip's outlets switch individually; the parent has no single on/off
                is_on = None
            else:
                relay_state = _info_value(sys_info, "relay_state")
                is_on = relay_state == 1 if relay_state is not None else None

        return DeviceSummary(
            device_id=device.device_id,
            child_id=device.child_id,
            alias=decode_alias(device.get_alias()),
            model=parent.device_info.device_model if parent else "",
            device_type=device.model_type.name,
            cloud=getattr(device, "cloud_type", "kasa") or "kasa",
            is_online=is_online,
            is_on=is_on,
            has_emeter=device.has_emeter(),
            rssi=rssi,
        )

    async def device_detail(self, device_id: str, child_id: str | None = None) -> DeviceDetail:
        device = self._find_device(device_id, child_id)
        parents = self._parents()
        parent = parents.get(device_id)
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

        # Build the shared summary fields through the single producer so
        # GET /devices and GET /devices/{id} can't disagree about is_on/rssi.
        summary = self._summarize(device, parents, {device_id: sys_info})
        return DeviceDetail(
            **summary.model_dump(),
            sys_info=jsonify(sys_info),
            net_info=jsonify(net_info),
        )

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
