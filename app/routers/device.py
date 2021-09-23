import json
from fastapi import APIRouter
from fastapi import Depends

from dependencies import oauth2_scheme
from dependencies import root_path
from services import TPLinkService
from models import DeviceResponse, DeviceSystemInfoResponse

router = APIRouter(
    prefix=f'{root_path}/devices',
    tags=['devices'],
    dependencies=[],
    responses={404: {'description': 'Not found'}}
)

def get_service(token: str = Depends(oauth2_scheme)):
    tplink_service = TPLinkService()
    tplink_service.set_auth_token(token)
    return tplink_service

@router.get('', response_model=DeviceResponse)
def get_devices(tplink_service: TPLinkService = Depends(get_service)):
    device_data = tplink_service.get_devices()

    print(json.dumps(device_data))

    return {
        'data': device_data
    }

@router.get('/{device_id}/systeminfo', response_model=DeviceSystemInfoResponse)
def get_devices(device_id, tplink_service: TPLinkService = Depends(get_service)):
    device_data = tplink_service.get_device_sys_info(device_id)

    print(json.dumps(device_data))

    return {
        'data': device_data
    }
