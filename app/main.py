import time
from fastapi import FastAPI

try:
    from routers import user, device_power, device
    from dependencies import root_path
except ImportError:
    from .routers import user, device_power, device
    from .dependencies import root_path


# Note that root_path is not implemented via FastAPI(root_path='route') intentionally.
# This is due to the behavior of Uvicorn in overwriting the root_path.
# https://fastapi.tiangolo.com/advanced/behind-a-proxy/
app = FastAPI()
app.include_router(user.router)
app.include_router(device_power.router)
app.include_router(device.router)


@app.get(f'{root_path}/time')
def get_current_time():
    return {'time': time.time()}
