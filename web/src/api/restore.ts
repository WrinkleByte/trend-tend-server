import { apiUpload } from "./client";

export interface RestoreSummary {
  assets: number;
  fuel_logs: number;
  maintenance_records: number;
  maintenance_schedules: number;
  attachments: number;
  skipped_attachments: number;
}

export interface RestoreConflict {
  existing_assets: number;
  existing_fuel_logs: number;
  existing_maintenance_records: number;
  existing_maintenance_schedules: number;
}

// Restores a backup zip (JSON + optional attachments/ folder) produced by
// any platform's export feature -- seeds the caller's household from
// scratch with freshly generated ids, never reusing the backup's own ids.
// Blocked with a 409 (whose body is a RestoreConflict) if the household
// already has data, unless force is set.
export function restoreBackup(file: File, force = false): Promise<RestoreSummary> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("force", String(force));
  return apiUpload(`/import/restore`, formData);
}
