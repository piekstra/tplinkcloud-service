from typing import List, Optional
from pydantic import BaseModel


class DeviceInfo(BaseModel):
    device_type: str
    role: int
    fw_ver: str
    device_region: str
    device_id: str
    device_name: str
    device_hw_ver: str
    alias: str
    device_mac: str
    oem_id: str
    device_model: str
    hw_id: str
    fw_id: str
    is_same_region: Optional[bool]
    status: int


class Device(BaseModel):
    device_id: str
    device_info: DeviceInfo


class DeviceResponse(BaseModel):
    data: List[Device] = []
