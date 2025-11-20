import os
from datetime import datetime, timedelta
from typing import Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import Session, select

from .database import get_session
from .models import User


def _load_secret_value(env_key: str, file_env_key: str, default: Optional[str] = None) -> Optional[str]:
    """Load a sensitive value from an environment variable or a file path."""

    file_path = os.getenv(file_env_key)
    if file_path and os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    env_value = os.getenv(env_key)
    if env_value:
        return env_value
    return default


SECRET_KEY = _load_secret_value("SECRET_KEY", "SECRET_KEY_FILE")
if not SECRET_KEY or SECRET_KEY == "change_me":
    raise RuntimeError("SECRET_KEY must be provided via SECRET_KEY or SECRET_KEY_FILE for secure operation.")

ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_MINUTES = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "10080"))

DEFAULT_ADMIN_USERNAME = _load_secret_value("DEFAULT_ADMIN_USERNAME", "DEFAULT_ADMIN_USERNAME_FILE", "admin")
DEFAULT_ADMIN_PASSWORD = _load_secret_value("DEFAULT_ADMIN_PASSWORD", "DEFAULT_ADMIN_PASSWORD_FILE")
AUTO_CREATE_ADMIN = os.getenv("AUTO_CREATE_ADMIN", "false").lower() == "true"
ADMIN_BOOTSTRAP_SECRET = _load_secret_value("ADMIN_BOOTSTRAP_SECRET", "ADMIN_BOOTSTRAP_SECRET_FILE")


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
revoked_refresh_tokens: set[str] = set()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def get_user_by_username(session: Session, username: str) -> Optional[User]:
    statement = select(User).where(User.username == username)
    return session.exec(statement).first()


def create_user(session: Session, username: str, password: str, role: str = "user") -> User:
    user = User(username=username, password_hash=hash_password(password), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def has_any_user(session: Session) -> bool:
    return session.exec(select(User)).first() is not None


def ensure_default_admin(session: Session) -> None:
    """Create an admin account if explicitly enabled and no users exist."""

    if has_any_user(session):
        return

    if not AUTO_CREATE_ADMIN:
        # Explicit opt-in required; bootstrap endpoint can be used instead.
        return

    if not DEFAULT_ADMIN_PASSWORD:
        raise RuntimeError(
            "AUTO_CREATE_ADMIN is true but DEFAULT_ADMIN_PASSWORD/DEFAULT_ADMIN_PASSWORD_FILE is not set."
        )

    create_user(session, DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD, role="admin")


def validate_bootstrap_secret(provided: str) -> None:
    if not ADMIN_BOOTSTRAP_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bootstrap secret is not configured on the server.",
        )
    if provided != ADMIN_BOOTSTRAP_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid bootstrap secret")


def authenticate_user(session: Session, username: str, password: str) -> Optional[User]:
    user = get_user_by_username(session, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: Dict) -> str:
    expire = datetime.utcnow() + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode = data.copy()
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)
) -> Dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        if username is None or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_username(session, username)
    if user is None:
        raise credentials_exception
    return {"id": user.id, "username": user.username, "role": user.role}


def revoke_refresh_token(token: str) -> None:
    revoked_refresh_tokens.add(token)


def is_refresh_revoked(token: str) -> bool:
    return token in revoked_refresh_tokens
