from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_user,
    get_current_user,
    get_user_by_username,
    has_any_user,
    is_refresh_revoked,
    revoke_refresh_token,
    validate_bootstrap_secret,
)
from ..database import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
  access_token: str
  refresh_token: str
  token_type: str = "bearer"
  user: dict


class LoginRequest(BaseModel):
  username: str
  password: str


class BootstrapRequest(BaseModel):
  username: str = Field(..., min_length=3)
  password: str = Field(..., min_length=8)
  bootstrap_token: str = Field(..., description="Secret token provided via ADMIN_BOOTSTRAP_SECRET(_FILE)")


class RefreshRequest(BaseModel):
  refresh_token: str


class LogoutRequest(BaseModel):
  refresh_token: str


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: Session = Depends(get_session)):
  user = authenticate_user(session, payload.username, payload.password)
  if not user:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

  access_token = create_access_token({"sub": payload.username})
  refresh_token = create_refresh_token({"sub": payload.username})
  return {
    "access_token": access_token,
    "refresh_token": refresh_token,
    "user": {"username": payload.username, "role": user.role},
  }


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, session: Session = Depends(get_session)):
  if is_refresh_revoked(payload.refresh_token):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

  from jose import JWTError, jwt
  from ..auth import ALGORITHM, SECRET_KEY

  try:
    decoded = jwt.decode(payload.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
    username = decoded.get("sub")
    if decoded.get("type") != "refresh":
      raise HTTPException(status_code=400, detail="Invalid token type")
  except JWTError:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

  user = get_user_by_username(session, username) if username else None
  if not user:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

  access_token = create_access_token({"sub": username})
  new_refresh = create_refresh_token({"sub": username})
  return {
    "access_token": access_token,
    "refresh_token": new_refresh,
    "user": {"username": username, "role": user.role},
  }


@router.post("/bootstrap", response_model=TokenResponse)
async def bootstrap(payload: BootstrapRequest, session: Session = Depends(get_session)):
  if has_any_user(session):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bootstrap already completed")

  validate_bootstrap_secret(payload.bootstrap_token)

  user = create_user(session, payload.username, payload.password, role="admin")

  access_token = create_access_token({"sub": payload.username})
  refresh_token = create_refresh_token({"sub": payload.username})

  return {
    "access_token": access_token,
    "refresh_token": refresh_token,
    "user": {"username": user.username, "role": user.role},
  }


@router.post("/logout")
async def logout(payload: LogoutRequest):
  revoke_refresh_token(payload.refresh_token)
  return {"status": "revoked"}


@router.get("/me")
async def me(current_user: Annotated[dict, Depends(get_current_user)]):
  return {"username": current_user.get("username", "admin"), "role": current_user.get("role", "user")}
