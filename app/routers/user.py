from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.dependencies import Gateway, root_path
from app.models import UserAuthToken

router = APIRouter(
    # Changing this prefix will affect the oauth2_scheme
    prefix=f"{root_path}/user",
    tags=["user"],
)


# Changing this route will affect the oauth2_scheme
@router.post("/token", response_model=UserAuthToken)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    gateway: Gateway,
    # When TP-Link demands MFA, the login response is a 401 with
    # mfa_required=true; resubmit the same form with this extra field.
    mfa_code: Annotated[str | None, Form()] = None,
):
    auth_token = await gateway.login(form_data.username, form_data.password, mfa_code=mfa_code)
    if not auth_token:
        # The header here is required by the OAuth2 spec
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # This return type and keys are required by the OAuth2 spec
    return {
        "access_token": auth_token,
        "token_type": "bearer",
    }
