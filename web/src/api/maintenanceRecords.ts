import { apiFetch } from "./client";
import type { MaintenanceRecord, MaintenanceRecordCreateInput } from "./types";

export function listMaintenanceRecords(assetId?: string): Promise<MaintenanceRecord[]> {
  const query = assetId ? `?asset_id=${encodeURIComponent(assetId)}` : "";
  return apiFetch(`/maintenance-records${query}`);
}

export function createMaintenanceRecord(input: MaintenanceRecordCreateInput): Promise<MaintenanceRecord> {
  return apiFetch("/maintenance-records", { method: "POST", body: JSON.stringify(input) });
}

export function deleteMaintenanceRecord(id: string): Promise<void> {
  return apiFetch(`/maintenance-records/${id}`, { method: "DELETE" });
}

export async function createMaintenanceRecordsBulk(
  records: MaintenanceRecordCreateInput[],
): Promise<{ imported: number; errors: number }> {
  let imported = 0;
  let errors = 0;

  for (const record of records) {
    try {
      await createMaintenanceRecord(record);
      imported++;
    } catch (error) {
      errors++;
      console.error("Failed to import maintenance record:", error);
    }
  }

  return { imported, errors };
}
