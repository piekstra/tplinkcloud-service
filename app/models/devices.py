from typing import Literal

from pydantic import BaseModel


class DeviceSummary(BaseModel):
    device_id: str
    # Set for power-strip outlets (HS300/KP303/EP40 children)
    child_id: str | None = None
    alias: str
    model: str
    device_type: str
    # Which TP-Link cloud the device lives on
    cloud: str = "kasa"
    is_online: bool
    # None when the device is offline or its state could not be read
    is_on: bool | None = None
    has_emeter: bool
    rssi: int | None = None


class DeviceListResponse(BaseModel):
    data: list[DeviceSummary] = []


class DeviceDetail(DeviceSummary):
    sys_info: dict | None = None
    net_info: dict | None = None


class DeviceDetailResponse(BaseModel):
    data: DeviceDetail


class DeviceSystemInfoResponse(BaseModel):
    data: dict | None = None


class PowerActionRequest(BaseModel):
    action: Literal["on", "off", "toggle"]


class PowerActionResponse(BaseModel):
    device_id: str
    child_id: str | None = None
    is_on: bool | None = None
