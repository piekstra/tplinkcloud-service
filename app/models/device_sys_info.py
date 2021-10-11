from pydantic import BaseModel


class DeviceSystemInfo(BaseModel):
    hw_ver: str
    err_code: int
    device_id: str
    updating: int
    led_off: int
    feature: str
    on_time: int
    relay_state: int
    oem_id: str
    alias: str
    model: str
    dev_name: str
    active_mode: str
    hw_id: str
    sw_ver: str


class DeviceSystemInfoResponse(BaseModel):
    data: DeviceSystemInfo
