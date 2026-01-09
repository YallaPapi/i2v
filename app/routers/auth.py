"""Authentication router for signup, login, and token management."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.models import User, UserRole, UserTier
from app.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["auth"])


# ============== Schemas ==============


class SignupRequest(BaseModel):
    """Request schema for user signup."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    name: Optional[str] = Field(None, max_length=255)


class LoginRequest(BaseModel):
    """Request schema for user login."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response schema for authentication tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    """Response schema for user data."""
    id: int
    email: str
    name: Optional[str]
    role: str
    tier: str
    credits_balance: int
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Combined response for login/signup with tokens and user."""
    user: UserResponse
    tokens: TokenResponse


class RefreshRequest(BaseModel):
    """Request schema for token refresh."""
    refresh_token: str


# ============== Endpoints ==============


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """
    Register a new user account.

    - Creates user with default 'manager' role and 'starter' tier
    - Returns access and refresh tokens for immediate login
    """
    # Check if email already exists
    existing = db.query(User).filter(User.email == request.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user
    user = User(
        email=request.email.lower(),
        hashed_password=hash_password(request.password),
        name=request.name,
        role=UserRole.MANAGER.value,
        tier=settings.default_user_tier,
        credits_balance=settings.default_user_credits,
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("User created", user_id=user.id, email=user.email)

    # Generate tokens
    tokens = _create_tokens(user)

    return AuthResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            tier=user.tier,
            credits_balance=user.credits_balance,
            is_active=user.is_active,
            created_at=user.created_at.isoformat(),
        ),
        tokens=tokens,
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user and return tokens.

    - Validates email and password
    - Returns access and refresh tokens on success
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.email.lower()).first()
    if not user:
        # Use same error message to prevent email enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password
    if not verify_password(request.password, user.hashed_password):
        logger.warning("Failed login attempt", email=request.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Update last login time
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("User logged in", user_id=user.id, email=user.email)

    # Generate tokens
    tokens = _create_tokens(user)

    return AuthResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            tier=user.tier,
            credits_balance=user.credits_balance,
            is_active=user.is_active,
            created_at=user.created_at.isoformat(),
        ),
        tokens=tokens,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token.

    - Validates refresh token
    - Returns new access and refresh tokens
    """
    try:
        payload = decode_token(request.refresh_token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Check token type
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # Get user
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Generate new tokens
    return _create_tokens(user)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: User = Depends(get_current_user)):
    """Get current authenticated user's information."""
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        tier=user.tier,
        credits_balance=user.credits_balance,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )


@router.post("/logout")
async def logout(user: User = Depends(get_current_user)):
    """
    Logout user (client-side token invalidation).

    Note: With JWT, logout is handled client-side by discarding tokens.
    This endpoint exists for logging and future token blacklisting if needed.
    """
    logger.info("User logged out", user_id=user.id, email=user.email)
    return {"message": "Logged out successfully"}


# ============== Helpers ==============


def _create_tokens(user: User) -> TokenResponse:
    """Create access and refresh tokens for a user."""
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )
