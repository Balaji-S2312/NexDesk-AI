from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.api_v1 import api_router
from app.database.init_db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nexdesk.startup")

# Ensure tables & seed accounts are initialized
init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify/refresh database initialization on startup
    init_db()
    warnings = settings.validate_runtime_settings()
    for warn in warnings:
        logger.warning("Production config notice: %s", warn)
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="NexDesk AI - Agentic Generative AI-powered IT Service Management Platform",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router with /api prefix -> /api/health, /api/auth/register, etc.
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Welcome to NexDesk AI API",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health",
        "auth": f"{settings.API_V1_STR}/auth/login"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
