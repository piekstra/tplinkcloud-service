# tplinkcloud-service

A REST API for monitoring and controlling TP-Link Kasa smart devices through the
[TP-Link cloud](https://www.tplinkcloud.com/), built on
[tplink-cloud-api](https://github.com/piekstra/tplink-cloud-api). No local network
access to the devices is required.

The primary consumer is [tplink-kasa-ui](https://github.com/piekstra/tplink-kasa-ui).

## Auth model

Stateless pass-through: `POST /api/v1/user/token` forwards your Kasa credentials to the
TP-Link cloud and returns TP-Link's own session token as the bearer token. The service
stores nothing — every request is authorized by TP-Link when the token is used. When the
token expires, requests return `401` and the client logs in again.

## API

All routes are prefixed with `/api/v1`.

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/time` | none | Health check; returns server epoch time |
| POST | `/user/token` | none | Login (OAuth2 password form) → bearer token |
| GET | `/devices` | bearer | All devices, power-strip outlets flattened alongside their parent. Filters: `name`, `model`, `state=on\|off\|offline` |
| GET | `/devices/{device_id}` | bearer | Device detail incl. raw sys_info and net info (`child_id` query param for strip outlets) |
| GET | `/devices/{device_id}/systeminfo` | bearer | Raw sys_info only |
| POST | `/devices/{device_id}/power` | bearer | Body `{"action": "on"\|"off"\|"toggle"}`; `child_id` query param for strip outlets. `409` if the device is offline |
| GET | `/power/devices/current` | bearer | Realtime power for emeter devices; optional `named` substring filter |
| GET | `/power/devices/day` | bearer | Daily energy (current + previous month) |
| GET | `/power/devices/month` | bearer | Monthly energy (current + previous year) |

Error mapping: TP-Link auth failures → `401`, unknown device → `404`, device offline on a
control call → `409`, TP-Link cloud unreachable/erroring → `502`, cloud timeout → `504`.

## Configuration (env vars)

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEVICE_CACHE_TTL` | `60` | Seconds a token's device list is cached before refetching |
| `DEVICE_CACHE_MAX_SESSIONS` | `32` | Max distinct tokens held in the in-process session/device-list cache |
| `CLOUD_TIMEOUT_SECONDS` | `30` | Ceiling for any fan-out to the TP-Link cloud |
| `CORS_ORIGINS` | `[]` | JSON list of allowed origins; empty disables CORS (same-origin deployments behind a reverse proxy don't need it) |
| `ALLOWED_CLOUD_HOST_SUFFIXES` | `[".tplinkcloud.com"]` | Host suffixes a session token's regional API host may use (SSRF guard) |
| `TPLINK_CLOUD_API_HOST` | _(library default)_ | Override the TP-Link cloud host; leave unset in production (testing only) |
| `LOG_LEVEL` | `INFO` | Python logging level |

## Development

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync                                # install deps
uv run uvicorn app.main:app --reload   # run on :8000
uv run pytest                          # tests
uv run ruff check app tests && uv run ruff format app tests
```

Interactive API docs: http://localhost:8000/docs

## Docker

```sh
docker build -t tplinkcloud-service .
docker run -p 8000:8000 tplinkcloud-service
```

Images are published to `ghcr.io/piekstra/tplinkcloud-service` on `v*` tags.
Run a single container per deployment: the device-list cache is in-process, so multiple
workers would each maintain their own (harmless, but wasteful of TP-Link cloud calls).

## Vendor-service convention

This service is the TP-Link implementation of a small convention intended to be shared by
future vendor services (govee, roomba, ...) behind a multi-vendor home dashboard:

- `POST /user/token` — vendor login → opaque bearer token, nothing stored server-side
- `GET /devices` — flat summaries: `device_id`, `child_id?`, `alias`, `is_online`, `is_on`, capabilities
- `POST /devices/{id}/power` — imperative control, `409` when unreachable
- Vendor error codes mapped onto `401/404/409/502/504`
