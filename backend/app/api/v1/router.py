from fastapi import APIRouter

from app.api.v1 import assets, auth, households, maintenance_records, maintenance_schedules

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(households.router)
api_router.include_router(assets.router)
api_router.include_router(maintenance_records.router)
api_router.include_router(maintenance_schedules.router)
