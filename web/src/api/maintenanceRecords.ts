import { apiFetch } from "./client";
import type { MaintenanceRecord, MaintenanceRecordCreateInput } from "./types";

export function listMaintenanceRecords(assetId: string): Promise<MaintenanceRecord[]> {
  return apiFetch(`/maintenance-records?asset_id=${assetId}`);
}

export function createMaintenanceRecord(input: MaintenanceRecordCreateInput): Promise<MaintenanceRecord> {
  return apiFetch("/maintenance-records", { method: "POST", body: JSON.stringify(input) });
}

export function deleteMaintenanceRecord(id: string): Promise<void> {
  return apiFetch(`/maintenance-records/${id}`, { method: "DELETE" });
}
