from typing import List, Optional
from pydantic import BaseModel

class DeviceInfo(BaseModel):
    device_type: str        # "IOT.SMARTPLUGSWITCH",
    role: int               # 0,
    fw_ver: str             # "1.0.17 Build 210506 Rel.075231",
    #"app_server_url":"https://use1-wap.tplinkcloud.com",
    device_region: str      # "us-east-1",
    device_id: str          # "80066F589AF56C3BED9C4C7F208433931DDF7861",
    device_name: str        # "Smart Wi-Fi Plug Mini",
    device_hw_ver: str      # "1.0",
    alias: str              # "Wall-E",
    device_mac: str         # "C0C9E30E44C7",
    oem_id: str             # "9FDE0C9E37EDF4495F681216FEFB0CFB",
    device_model: str       # "KP115(US)",
    hw_id: str              # "3E2B9A976B98DCFC5C83D11C8CEF7510",
    fw_id: str              # "00000000000000000000000000000000",
    is_same_region: Optional[bool]   # true,
    status: int             # 1

class Device(BaseModel):
    device_id: str
    device_info: DeviceInfo

class DeviceResponse(BaseModel):
    data: List[Device] = []