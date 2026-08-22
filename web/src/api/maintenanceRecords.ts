import type { BulkImportResult } from "./fuelLogs";
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
): Promise<BulkImportResult> {
  if (records.length === 0) return { imported: 0, errors: 0, errorDetails: [] };
  // One request for the whole batch instead of N sequential POSTs (Vikunja
  // #39) -- each row gets its own server-side SAVEPOINT, so one bad row
  // doesn't roll back the rest.
  const results = await apiFetch<Array<{ index: number; status: "created" | "error"; error?: string }>>(
    "/maintenance-records/bulk",
    { method: "POST", body: JSON.stringify({ items: records }) },
  );
  const errorDetails = results.filter((r) => r.status === "error").map((r) => r.error ?? "Unknown error");
  return { imported: results.length - errorDetails.length, errors: errorDetails.length, errorDetails };
}
