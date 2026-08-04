from fastapi import APIRouter

from app.api.v1 import (
    api_tokens,
    assets,
    attachments,
    auth,
    households,
    maintenance_records,
    maintenance_schedules,
    sync,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(households.router)
api_router.include_router(assets.router)
api_router.include_router(maintenance_records.router)
api_router.include_router(maintenance_schedules.router)
api_router.include_router(attachments.router)
api_router.include_router(api_tokens.router)
api_router.include_router(sync.router)
