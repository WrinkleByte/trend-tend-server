from pydantic import BaseModel


class RestoreSummary(BaseModel):
    """What actually landed in the household after a restore -- returned so
    the caller can show the user something more useful than a bare 200."""

    assets: int
    fuel_logs: int
    maintenance_records: int
    maintenance_schedules: int
    attachments: int
    # fuel_log/trip_log attachments have no backend join table to restore
    # into (see RecordAttachment's doc comment in maintenance_record.py --
    # backend attachments only link to a maintenance_record or an asset
    # photo) -- counted separately rather than silently dropped, so a
    # backup containing them doesn't look like it "fully" restored.
    skipped_attachments: int


class RestoreConflict(BaseModel):
    """409 body when the household already has data and the caller didn't
    pass force=true -- tells them exactly what's blocking it rather than a
    bare "Conflict"."""

    existing_assets: int
    existing_fuel_logs: int
    existing_maintenance_records: int
    existing_maintenance_schedules: int
