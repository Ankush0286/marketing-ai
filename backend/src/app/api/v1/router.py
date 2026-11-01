from fastapi import APIRouter

from app.modules.accounts.router import router as accounts_router
from app.modules.campaigns.router import router as campaigns_router
from app.modules.copilot.router import router as copilot_router
from app.modules.history.router import router as history_router
from app.modules.outreach.router import router as outreach_router
from app.modules.triggers.router import router as triggers_router

api_v1_router = APIRouter()

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

api_v1_router.include_router(
    triggers_router,
    prefix="/triggers",
    tags=["Triggers"],
)

api_v1_router.include_router(
    outreach_router,
    prefix="/outreach",
    tags=["Outreach"],
)

api_v1_router.include_router(
    history_router,
    prefix="/history",
    tags=["History"],
)

api_v1_router.include_router(
    copilot_router,
    prefix="/copilot",
    tags=["Copilot"],
)
