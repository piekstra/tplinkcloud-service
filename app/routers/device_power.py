import json
from fastapi import APIRouter
from fastapi import Depends

try:
    from dependencies import oauth2_scheme, root_path
    from services import TPLinkService
    from models import DevicesPowerCurrentResponse, DevicesPowerDayResponse, DevicesPowerMonthResponse
except ImportError:
    from ..dependencies import oauth2_scheme, root_path
    from ..services import TPLinkService
    from ..models import DevicesPowerCurrentResponse, DevicesPowerDayResponse, DevicesPowerMonthResponse

router = APIRouter(
    prefix=f'{root_path}/power/devices',
    tags=['power'],
    dependencies=[],
    responses={404: {'description': 'Not found'}}
)


def get_service(token: str = Depends(oauth2_scheme)):
    tplink_service = TPLinkService()
    tplink_service.set_auth_token(token)
    return tplink_service


@router.get('/current', response_model=DevicesPowerCurrentResponse)
def get_devices_power_current(named: str, tplink_service: TPLinkService = Depends(get_service)):
    power_data = tplink_service.get_power_data_current(
        device_filter=named
    )

    print(json.dumps(power_data))

    return {
        'data': power_data
    }


@router.get('/day', response_model=DevicesPowerDayResponse)
def get_devices_power_day(named: str, tplink_service: TPLinkService = Depends(get_service)):
    power_data = tplink_service.get_power_data_day(
        device_filter=named
    )

    return {
        'data': power_data
    }


@router.get('/month', response_model=DevicesPowerMonthResponse)
def get_devices_power_month(named: str, tplink_service: TPLinkService = Depends(get_service)):
    power_data = tplink_service.get_power_data_month(
        device_filter=named
    )

    return {
        'data': power_data
    }
