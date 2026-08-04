import { apiFetch } from "./client";
import type { MaintenanceSchedule, MaintenanceScheduleCreateInput } from "./types";

export function listMaintenanceSchedules(assetId: string): Promise<MaintenanceSchedule[]> {
  return apiFetch(`/maintenance-schedules?asset_id=${assetId}`);
}

export function createMaintenanceSchedule(input: MaintenanceScheduleCreateInput): Promise<MaintenanceSchedule> {
  return apiFetch("/maintenance-schedules", { method: "POST", body: JSON.stringify(input) });
}

export function deleteMaintenanceSchedule(id: string): Promise<void> {
  return apiFetch(`/maintenance-schedules/${id}`, { method: "DELETE" });
}
