from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

from app.services.tplink_service import TPLinkGateway, TPLinkSession

root_path = "/api/v1"

# Note that this has to have parity with the `user` router's `token` endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{root_path}/user/token")


def get_gateway(request: Request) -> TPLinkGateway:
    return request.app.state.gateway


async def get_session(
    token: Annotated[str, Depends(oauth2_scheme)],
    gateway: Annotated[TPLinkGateway, Depends(get_gateway)],
) -> TPLinkSession:
    return await gateway.session(token)


Gateway = Annotated[TPLinkGateway, Depends(get_gateway)]
Session = Annotated[TPLinkSession, Depends(get_session)]
