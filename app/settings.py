from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Override the TP-Link cloud hosts (testing only); None uses the library defaults
    tplink_cloud_api_host: str | None = None
    # The session token carries the account's regional API host, which the
    # library uses as the outbound request destination. Restrict it to TP-Link's
    # own domains so a forged/tampered token can't redirect credentialed
    # requests at an arbitrary host (SSRF). Widen only to add a test host.
    allowed_cloud_host_suffixes: list[str] = [".tplinkcloud.com"]
    # How long a token's device list (and manager) is reused before refetching
    # from the TP-Link cloud. Also bounds how long a renamed/added device takes
    # to appear.
    device_cache_ttl: int = 60
    device_cache_max_sessions: int = 32
    # Ceiling for a full sys_info fan-out across all devices in one request.
    cloud_timeout_seconds: float = 30.0
    # JSON list, e.g. CORS_ORIGINS='["https://home.example.com"]'.
    # Empty (the default) disables CORS entirely; same-origin deployments
    # behind the nginx proxy don't need it.
    cors_origins: list[str] = []
    log_level: str = "INFO"
