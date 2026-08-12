from typing import Literal

from fastapi import APIRouter

from app.dependencies import Session, root_path
from app.models import (
    DeviceDetailResponse,
    DeviceListResponse,
    DeviceSystemInfoResponse,
    PowerActionRequest,
    PowerActionResponse,
)

router = APIRouter(
    prefix=f"{root_path}/devices",
    tags=["devices"],
)


@router.get("", response_model=DeviceListResponse)
async def list_devices(
    session: Session,
    name: str | None = None,
    model: str | None = None,
    state: Literal["on", "off", "offline"] | None = None,
):
    return {"data": await session.device_summaries(name=name, model=model, state=state)}


@router.get("/{device_id}", response_model=DeviceDetailResponse)
async def get_device(session: Session, device_id: str, child_id: str | None = None):
    return {"data": await session.device_detail(device_id, child_id)}


@router.get("/{device_id}/systeminfo", response_model=DeviceSystemInfoResponse)
async def get_device_system_info(session: Session, device_id: str, child_id: str | None = None):
    return {"data": await session.device_sys_info(device_id, child_id)}


@router.post("/{device_id}/power", response_model=PowerActionResponse)
async def set_device_power(
    session: Session,
    device_id: str,
    request: PowerActionRequest,
    child_id: str | None = None,
):
    return await session.set_power(device_id, request.action, child_id)
