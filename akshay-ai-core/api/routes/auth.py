"""
============================================================
AKSHAY AI CORE — Authentication Routes
============================================================
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from core.config import settings
from core.security.auth_manager import auth_manager
from core.utils.logger import get_logger, audit_logger

logger = get_logger("api.auth")
router = APIRouter()


class PINLoginRequest(BaseModel):
    """PIN login request model."""
    username: str
    pin: str


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    auth_method: str


class UserResponse(BaseModel):
    """User info response model."""
    user_id: str
    username: str
    role: str
    permissions: list[str]
    last_login: Optional[datetime]


@router.post("/pin-login", response_model=TokenResponse)
async def login_with_pin(request: PINLoginRequest, req: Request):
    """
    Authenticate using PIN code.
    
    Args:
        request: PIN login credentials
        
    Returns:
        JWT access token
    """
    # In production, fetch user from database
    # For now, use mock validation
    
    # Validate PIN (mock - would check database)
    if len(request.pin) < settings.PIN_MIN_LENGTH:
        audit_logger.log(
            action="login_failed",
            details={"username": request.username, "reason": "invalid_pin"},
            status="failure",
            ip_address=req.client.host if req.client else None,
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create session token
    token = auth_manager.create_session_token(
        user_id=request.username,
        auth_method="pin",
    )
    
    audit_logger.log(
        action="login_success",
        user_id=request.username,
        details={"method": "pin"},
        ip_address=req.client.host if req.client else None,
    )
    
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRY_HOURS * 3600,
        user_id=request.username,
        auth_method="pin",
    )


@router.post("/face-login", response_model=TokenResponse)
async def login_with_face(req: Request):
    """
    Authenticate using face recognition.
    
    Initiates camera capture and face matching.
    
    Returns:
        JWT access token if face matches
    """
    user_id = await auth_manager.authenticate_face(timeout=30)
    
    if not user_id:
        audit_logger.log(
            action="login_failed",
            details={"method": "face", "reason": "no_match"},
            status="failure",
            ip_address=req.client.host if req.client else None,
        )
        raise HTTPException(status_code=401, detail="Face authentication failed")
    
    token = auth_manager.create_session_token(
        user_id=user_id,
        auth_method="face",
    )
    
    audit_logger.log(
        action="login_success",
        user_id=user_id,
        details={"method": "face"},
        ip_address=req.client.host if req.client else None,
    )
    
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRY_HOURS * 3600,
        user_id=user_id,
        auth_method="face",
    )


@router.post("/logout")
async def logout(req: Request):
    """
    Logout and invalidate session.
    
    Returns:
        Success message
    """
    auth_header = req.headers.get("Authorization")
    if auth_header:
        try:
            _, token = auth_header.split()
            auth_manager.invalidate_session(token)
        except ValueError:
            pass
    
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user(req: Request):
    """
    Get current authenticated user info.
    
    Returns:
        User information
    """
    user_id = getattr(req.state, "user_id", None)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # In production, fetch from database
    return UserResponse(
        user_id=user_id,
        username=user_id,
        role="admin",  # Would come from database
        permissions=["*"],  # Would come from database
        last_login=datetime.utcnow(),
    )


@router.post("/refresh")
async def refresh_token(req: Request):
    """
    Refresh an expiring token.
    
    Returns:
        New JWT access token
    """
    user_id = getattr(req.state, "user_id", None)
    auth_method = getattr(req.state, "auth_method", "token")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_manager.create_session_token(
        user_id=user_id,
        auth_method=auth_method,
    )
    
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRY_HOURS * 3600,
        user_id=user_id,
        auth_method=auth_method,
    )


@router.post("/lock")
async def lock_system(req: Request):
    """
    Emergency lock the system.
    
    Returns:
        Lock confirmation
    """
    user_id = getattr(req.state, "user_id", None)
    
    audit_logger.log(
        action="system_locked",
        user_id=user_id,
        details={"method": "api"},
        ip_address=req.client.host if req.client else None,
    )
    
    # In production, this would:
    # 1. Invalidate all sessions
    # 2. Trigger UI lock screen
    # 3. Stop sensitive operations
    
    return {"message": "System locked", "timestamp": datetime.utcnow().isoformat()}
