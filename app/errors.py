from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from tplinkcloud import (
    TPLinkAuthError,
    TPLinkCloudError,
    TPLinkMFARequiredError,
    TPLinkTokenExpiredError,
)


class InvalidServiceTokenError(Exception):
    """The bearer token is not one this service minted."""

    def __init__(self):
        super().__init__("Unrecognized bearer token; log in again")


class DeviceNotFoundError(Exception):
    def __init__(self, device_id: str, child_id: str | None = None):
        super().__init__(
            f"No device {device_id!r}" + (f" with child {child_id!r}" if child_id else "")
        )


class DeviceOfflineError(Exception):
    def __init__(self, device_id: str):
        super().__init__(f"Device {device_id!r} is offline")


def _unauthorized(detail: str, **extra) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": detail, **extra},
        headers={"WWW-Authenticate": "Bearer"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(TPLinkMFARequiredError)
    async def mfa_required(request: Request, exc: TPLinkMFARequiredError):
        # The login form can be resubmitted with an mfa_code field
        return _unauthorized(str(exc), mfa_required=True)

    @app.exception_handler(TPLinkAuthError)
    async def auth_error(request: Request, exc: TPLinkAuthError):
        return _unauthorized(str(exc))

    @app.exception_handler(TPLinkTokenExpiredError)
    async def token_expired(request: Request, exc: TPLinkTokenExpiredError):
        return _unauthorized(str(exc))

    @app.exception_handler(InvalidServiceTokenError)
    async def invalid_token(request: Request, exc: InvalidServiceTokenError):
        return _unauthorized(str(exc))

    @app.exception_handler(DeviceNotFoundError)
    async def not_found(request: Request, exc: DeviceNotFoundError):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(DeviceOfflineError)
    async def offline(request: Request, exc: DeviceOfflineError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @app.exception_handler(TPLinkCloudError)
    async def cloud_error(request: Request, exc: TPLinkCloudError):
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": str(exc)})

    @app.exception_handler(TimeoutError)
    async def timeout(request: Request, exc: TimeoutError):
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"detail": "Timed out waiting on the TP-Link cloud"},
        )
