from fastapi import APIRouter

from app.modules.accounts.router import router as accounts_router
from app.modules.campaigns.router import router as campaigns_router

api_v1_router = APIRouter()

# Register Domain Routers
api_v1_router.include_router(
    accounts_router,
    prefix="/accounts",
    tags=["Accounts"],
)

api_v1_router.include_router(
    campaigns_router,
    prefix="/campaigns",
    tags=["Campaigns"],
)
