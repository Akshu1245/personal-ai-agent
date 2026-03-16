"""
============================================================
AKSHAY AI CORE — FastAPI Application
============================================================
Main API server with WebSocket support, authentication,
and modular route registration.
============================================================
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.utils.logger import setup_logging, get_logger, audit_logger
from api.routes import auth, brain, plugins, automation, system
from api.middleware import RequestLoggingMiddleware, AuthenticationMiddleware

logger = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting AKSHAY AI CORE API server")
    setup_logging()
    
    # Initialize components
    from core.init_db import initialize_database
    await initialize_database()
    logger.info("Database initialized")
    
    # Load plugins
    from plugins import plugin_manager
    await plugin_manager.load_all_plugins()
    logger.info("Plugins loaded")
    
    # Start background services
    from automation.scheduler import scheduler
    await scheduler.start()
    logger.info("Scheduler started")
    
    audit_logger.log(
        action="system_startup",
        details={"version": settings.APP_VERSION},
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down AKSHAY AI CORE API server")
    
    # Stop scheduler
    await scheduler.stop()
    
    # Unload plugins
    await plugin_manager.unload_all_plugins()
    
    audit_logger.log(action="system_shutdown")
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Personal AI Operating System API",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware
app.add_middleware(RequestLoggingMiddleware)
if not settings.DEV_BYPASS_AUTH:
    app.add_middleware(AuthenticationMiddleware)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
    )
    
    audit_logger.log(
        action="api_error",
        details={
            "path": request.url.path,
            "method": request.method,
            "error": str(exc),
        },
        status="error",
        error_message=str(exc),
    )
    
    if settings.DEBUG:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "detail": str(exc),
                "type": type(exc).__name__,
            },
        )
    
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error"},
    )


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


# Root endpoint
@app.get("/", tags=["System"])
async def root():
    """API root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/api/docs" if settings.DEBUG else None,
    }


# Register routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(brain.router, prefix="/api/brain", tags=["AI Brain"])
app.include_router(plugins.router, prefix="/api/plugins", tags=["Plugins"])
app.include_router(automation.router, prefix="/api/automation", tags=["Automation"])
app.include_router(system.router, prefix="/api/system", tags=["System"])


# WebSocket endpoint for real-time communication
from api.websocket import websocket_manager

@app.websocket("/ws")
async def websocket_endpoint(websocket):
    """WebSocket endpoint for real-time communication."""
    await websocket_manager.handle_connection(websocket)
