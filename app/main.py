import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.dependencies import root_path
from app.errors import register_exception_handlers
from app.routers import device_power, devices, user
from app.services.tplink_service import TPLinkGateway
from app.settings import Settings


# Note that root_path is not implemented via FastAPI(root_path='route') intentionally.
# This is due to the behavior of Uvicorn in overwriting the root_path.
# https://fastapi.tiangolo.com/advanced/behind-a-proxy/
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(level=settings.log_level)

    app = FastAPI(title="TP-Link Kasa API Service", version="2.0.0")
    app.state.settings = settings
    app.state.gateway = TPLinkGateway(settings)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(app)
    app.include_router(user.router)
    app.include_router(devices.router)
    app.include_router(device_power.router)

    @app.get(f"{root_path}/time")
    def get_current_time():
        return {"time": time.time()}

    return app


app = create_app()
