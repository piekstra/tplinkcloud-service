from pydantic import BaseModel


class DevicePowerCurrent(BaseModel):
    # Values are floats because some devices (e.g. HS110) report unsuffixed
    # float readings that the library maps onto these fields unscaled.
    voltage_mv: float
    current_ma: float
    power_mw: float
    total_wh: float


class DevicePowerUsageCurrent(BaseModel):
    device_id: str
    child_id: str | None = None
    name: str
    # None when the device was offline at read time
    data: DevicePowerCurrent | None = None


class DevicesPowerCurrentResponse(BaseModel):
    data: list[DevicePowerUsageCurrent] = []


class DevicePowerDay(BaseModel):
    year: int
    month: int
    day: int
    energy_wh: float


class DevicePowerUsageDay(BaseModel):
    device_id: str
    child_id: str | None = None
    name: str
    data: list[DevicePowerDay] | None = []


class DevicesPowerDayResponse(BaseModel):
    data: list[DevicePowerUsageDay] = []


class DevicePowerMonth(BaseModel):
    year: int
    month: int
    energy_wh: float


class DevicePowerUsageMonth(BaseModel):
    device_id: str
    child_id: str | None = None
    name: str
    data: list[DevicePowerMonth] | None = []


class DevicesPowerMonthResponse(BaseModel):
    data: list[DevicePowerUsageMonth] = []
