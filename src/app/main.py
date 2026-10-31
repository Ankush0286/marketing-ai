from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.error_handlers import register_exception_handlers
from app.core.logging import get_logger
from app.modules.accounts.router import router as accounts_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for app startup and shutdown."""
    logger.info("Initializing Marketing AI Agent backend...")
    yield
    logger.info("Shutting down Marketing AI Agent backend...")


app = FastAPI(
    title="Marketing AI Agent",
    description="Offline-first autonomous marketing agent and social CRM",
    version="0.1.0",
    lifespan=lifespan,
    debug=getattr(settings, "DEBUG", False),
)

# 1. Register Centralized Exception Handlers
register_exception_handlers(app)

# 2. CORS Middleware (allows Vite dev server on port 5173 to reach the API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Healthcheck Endpoint
@app.get("/health", tags=["System"])
def healthcheck():
    return {"status": "ok", "app": "marketing-ai"}


# 4. Mount Domain Routers
app.include_router(
    accounts_router,
    prefix="/api/v1/accounts",
    tags=["Accounts"],
)
