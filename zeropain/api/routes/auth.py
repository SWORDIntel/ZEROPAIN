#!/usr/bin/env python3
"""
Authentication Routes
Login, logout, token refresh, user management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer

from ..auth import (
    authenticate_user,
    create_user_tokens,
    verify_token,
    revoke_token,
    get_current_active_user,
    require_admin,
    LoginRequest,
    User,
    Token,
    PasswordChangeRequest,
    get_password_hash,
    verify_password,
    get_user,
    fake_users_db,
    UserInDB
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
security = HTTPBearer()


@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest):
    """
    Login with username and password

    Returns JWT access and refresh tokens
    """
    user = authenticate_user(login_data.username, login_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )

    # Create tokens
    tokens = create_user_tokens(user)

    return tokens


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str):
    """
    Refresh access token using refresh token

    Returns new access and refresh tokens
    """
    # Verify refresh token
    token_data = verify_token(refresh_token, token_type="refresh")

    if token_data is None or token_data.username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Get user
    user = get_user(token_data.username)
    if user is None or user.disabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled"
        )

    # Create new tokens
    tokens = create_user_tokens(user)

    return tokens


@router.post("/logout")
async def logout(
    refresh_token: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Logout and revoke refresh token
    """
    revoke_token(refresh_token)

    return {"message": "Successfully logged out"}


@router.get("/me", response_model=User)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user information
    """
    return current_user


@router.post("/change-password")
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Change current user's password
    """
    # Get user with password
    user = get_user(current_user.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Verify old password
    if not verify_password(password_data.old_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password"
        )

    # Update password
    user.hashed_password = get_password_hash(password_data.new_password)
    # TODO: Save to database

    return {"message": "Password updated successfully"}


@router.get("/users", response_model=list[User])
async def list_users(admin_user: User = Depends(require_admin)):
    """
    List all users (admin only)
    """
    users = [
        User(**user.dict(exclude={"hashed_password"}))
        for user in fake_users_db.values()
    ]
    return users


@router.post("/users/create", response_model=User)
async def create_user(
    username: str,
    password: str,
    email: str = None,
    full_name: str = None,
    role: str = "user",
    admin_user: User = Depends(require_admin)
):
    """
    Create new user (admin only)
    """
    # Check if user exists
    if username in fake_users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    # Create user
    new_user = UserInDB(
        username=username,
        email=email,
        full_name=full_name,
        role=role,
        disabled=False,
        hashed_password=get_password_hash(password)
    )

    # Save to database
    fake_users_db[username] = new_user
    # TODO: Save to PostgreSQL

    return User(**new_user.dict(exclude={"hashed_password"}))


@router.delete("/users/{username}")
async def delete_user(
    username: str,
    admin_user: User = Depends(require_admin)
):
    """
    Delete user (admin only)
    """
    # Prevent deleting self
    if username == admin_user.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    # Check if user exists
    if username not in fake_users_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Delete user
    del fake_users_db[username]
    # TODO: Delete from PostgreSQL

    return {"message": f"User {username} deleted successfully"}


@router.put("/users/{username}/disable")
async def disable_user(
    username: str,
    disabled: bool,
    admin_user: User = Depends(require_admin)
):
    """
    Enable/disable user (admin only)
    """
    # Prevent disabling self
    if username == admin_user.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot disable your own account"
        )

    # Get user
    user = get_user(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update status
    user.disabled = disabled
    # TODO: Save to PostgreSQL

    status_text = "disabled" if disabled else "enabled"
    return {"message": f"User {username} {status_text} successfully"}
