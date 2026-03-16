"""
============================================================
AKSHAY AI CORE — API Middleware
============================================================
Custom middleware for logging, authentication, and rate limiting.
============================================================
"""

import time
from typing import Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings
from core.utils.logger import get_logger, audit_logger
from core.security.auth_manager import auth_manager

logger = get_logger("middleware")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all incoming requests."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid4())[:8]
        request.state.request_id = request_id
        
        # Log request
        start_time = time.time()
        
        logger.info(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log response
        logger.info(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        
        # Add headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        
        return response


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Verify authentication for protected routes."""
    
    # Routes that don't require authentication
    PUBLIC_PATHS = {
        "/",
        "/health",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
        "/api/auth/login",
        "/api/auth/face-login",
        "/api/auth/pin-login",
    }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip auth for public paths
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)
        
        # Skip auth for WebSocket (handled separately)
        if request.url.path.startswith("/ws"):
            return await call_next(request)
        
        # Get token from header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return Response(
                content='{"error": "Authorization header required"}',
                status_code=401,
                media_type="application/json",
            )
        
        # Extract token
        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                raise ValueError("Invalid auth scheme")
        except ValueError:
            return Response(
                content='{"error": "Invalid authorization header format"}',
                status_code=401,
                media_type="application/json",
            )
        
        # Verify token
        payload = auth_manager.verify_session_token(token)
        
        if not payload:
            return Response(
                content='{"error": "Invalid or expired token"}',
                status_code=401,
                media_type="application/json",
            )
        
        # Attach user info to request
        request.state.user_id = payload.get("sub")
        request.state.auth_method = payload.get("auth_method")
        
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._request_counts: dict = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get client identifier
        client_id = request.client.host if request.client else "unknown"
        
        # Get current minute
        current_minute = int(time.time() / 60)
        
        # Initialize or reset counter
        if client_id not in self._request_counts:
            self._request_counts[client_id] = {"minute": current_minute, "count": 0}
        
        if self._request_counts[client_id]["minute"] != current_minute:
            self._request_counts[client_id] = {"minute": current_minute, "count": 0}
        
        # Increment counter
        self._request_counts[client_id]["count"] += 1
        
        # Check rate limit
        if self._request_counts[client_id]["count"] > self.requests_per_minute:
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id,
                requests=self._request_counts[client_id]["count"],
            )
            return Response(
                content='{"error": "Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
            )
        
        return await call_next(request)
