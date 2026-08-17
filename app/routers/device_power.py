from fastapi import APIRouter

from app.dependencies import Session, root_path
from app.models import (
    DevicesPowerCurrentResponse,
    DevicesPowerDayResponse,
    DevicesPowerMonthResponse,
)

router = APIRouter(
    prefix=f"{root_path}/power/devices",
    tags=["power"],
)


@router.get("/current", response_model=DevicesPowerCurrentResponse)
async def get_devices_power_current(session: Session, named: str | None = None):
    return {"data": await session.power_usage_realtime(named)}


@router.get("/day", response_model=DevicesPowerDayResponse)
async def get_devices_power_day(session: Session, named: str | None = None):
    return {"data": await session.power_usage_day(named)}


@router.get("/month", response_model=DevicesPowerMonthResponse)
async def get_devices_power_month(session: Session, named: str | None = None):
    return {"data": await session.power_usage_month(named)}
