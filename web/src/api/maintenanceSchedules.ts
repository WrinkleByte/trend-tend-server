import { apiFetch } from "./client";
import type { MaintenanceSchedule, MaintenanceScheduleCreateInput, MaintenanceScheduleUpdateInput } from "./types";

export function listMaintenanceSchedules(assetId?: string): Promise<MaintenanceSchedule[]> {
  const query = assetId ? `?asset_id=${encodeURIComponent(assetId)}` : "";
  return apiFetch(`/maintenance-schedules${query}`);
}

export function createMaintenanceSchedule(input: MaintenanceScheduleCreateInput): Promise<MaintenanceSchedule> {
  return apiFetch("/maintenance-schedules", { method: "POST", body: JSON.stringify(input) });
}

export function updateMaintenanceSchedule(
  id: string,
  input: Partial<MaintenanceScheduleUpdateInput>,
): Promise<MaintenanceSchedule> {
  return apiFetch(`/maintenance-schedules/${id}`, { method: "PATCH", body: JSON.stringify(input) });
}

export function deleteMaintenanceSchedule(id: string): Promise<void> {
  return apiFetch(`/maintenance-schedules/${id}`, { method: "DELETE" });
}
