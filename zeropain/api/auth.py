#!/usr/bin/env python3
"""
Authentication and Authorization Module
JWT-based auth with Redis session storage
"""

from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import os
import redis

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security
security = HTTPBearer()

# Redis connection (for session management)
try:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_client = redis.from_url(redis_url, decode_responses=True)
except Exception as e:
    print(f"Warning: Redis connection failed: {e}")
    redis_client = None


# ============================================================================
# Pydantic Models
# ============================================================================

class User(BaseModel):
    """User model"""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: bool = False
    role: str = "user"  # admin, user, readonly


class UserInDB(User):
    """User with hashed password"""
    hashed_password: str


class Token(BaseModel):
    """Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token payload data"""
    username: Optional[str] = None
    role: Optional[str] = None


class LoginRequest(BaseModel):
    """Login request"""
    username: str
    password: str


class PasswordChangeRequest(BaseModel):
    """Password change request"""
    old_password: str
    new_password: str


# ============================================================================
# Password Utilities
# ============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password with bcrypt"""
    return pwd_context.hash(password)


# ============================================================================
# User Database (In-memory for demo, use PostgreSQL in production)
# ============================================================================

# TODO: Replace with PostgreSQL database
fake_users_db = {
    "admin": UserInDB(
        username="admin",
        email="admin@zeropain.com",
        full_name="Admin User",
        role="admin",
        disabled=False,
        hashed_password=get_password_hash("admin123")  # Change in production!
    ),
    "user": UserInDB(
        username="user",
        email="user@zeropain.com",
        full_name="Regular User",
        role="user",
        disabled=False,
        hashed_password=get_password_hash("user123")
    ),
}


def get_user(username: str) -> Optional[UserInDB]:
    """Get user from database"""
    # TODO: Query from PostgreSQL
    return fake_users_db.get(username)


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """Authenticate user credentials"""
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# ============================================================================
# JWT Token Management
# ============================================================================

def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def create_refresh_token(data: Dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    # Store in Redis for revocation capability
    if redis_client:
        key = f"refresh_token:{to_encode.get('sub')}"
        redis_client.setex(
            key,
            timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            encoded_jwt
        )

    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Check token type
        if payload.get("type") != token_type:
            return None

        username: str = payload.get("sub")
        role: str = payload.get("role")

        if username is None:
            return None

        return TokenData(username=username, role=role)

    except JWTError:
        return None


def revoke_token(token: str):
    """Revoke refresh token (add to blacklist)"""
    if redis_client:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if username:
                redis_client.delete(f"refresh_token:{username}")
        except JWTError:
            pass


# ============================================================================
# FastAPI Dependencies
# ============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """Get current authenticated user from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    token_data = verify_token(token, "access")

    if token_data is None or token_data.username is None:
        raise credentials_exception

    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception

    # Remove password from response
    return User(**user.dict(exclude={"hashed_password"}))


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active (non-disabled) user"""
    if current_user.disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Require admin role"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def require_user_or_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Require at least user role (not readonly)"""
    if current_user.role not in ["user", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    return current_user


# ============================================================================
# API Key Support (for programmatic access)
# ============================================================================

class APIKey(BaseModel):
    """API Key model"""
    key: str
    name: str
    user: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    permissions: list = []


def verify_api_key(api_key: str) -> Optional[User]:
    """Verify API key and return associated user"""
    # TODO: Implement with database
    # For now, return None (not implemented)
    return None


async def get_user_from_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[User]:
    """Get user from API key (X-API-Key header)"""
    api_key = credentials.credentials
    user = verify_api_key(api_key)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    return user


# ============================================================================
# Helper Functions
# ============================================================================

def create_user_tokens(user: UserInDB) -> Token:
    """Create access and refresh tokens for user"""
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}
    )

    refresh_token = create_refresh_token(
        data={"sub": user.username, "role": user.role}
    )

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )
