from fastapi import APIRouter

from app.api.v1 import (
    admin,
    api_tokens,
    assets,
    attachments,
    auth,
    fuel_logs,
    households,
    import_restore,
    instance_settings,
    maintenance_categories,
    maintenance_records,
    maintenance_schedules,
    sync,
    trip_logs,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(instance_settings.router)
api_router.include_router(admin.router)
api_router.include_router(households.router)
api_router.include_router(assets.router)
api_router.include_router(maintenance_categories.router)
api_router.include_router(maintenance_records.router)
api_router.include_router(maintenance_schedules.router)
api_router.include_router(fuel_logs.router)
api_router.include_router(trip_logs.router)
api_router.include_router(attachments.router)
api_router.include_router(import_restore.router)
api_router.include_router(api_tokens.router)
api_router.include_router(sync.router)
