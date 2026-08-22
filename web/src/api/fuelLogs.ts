import { apiFetch } from "./client";
import type { CreateFuelLogRequest, FuelLog } from "./types";

export function listFuelLogs(assetId?: string): Promise<FuelLog[]> {
  const query = assetId ? `?asset_id=${encodeURIComponent(assetId)}` : "";
  return apiFetch(`/fuel-logs${query}`);
}

export function getFuelLog(id: string): Promise<FuelLog> {
  return apiFetch(`/fuel-logs/${id}`);
}

export function createFuelLog(input: CreateFuelLogRequest): Promise<FuelLog> {
  return apiFetch("/fuel-logs", { method: "POST", body: JSON.stringify(input) });
}

export function updateFuelLog(id: string, input: Partial<CreateFuelLogRequest>): Promise<FuelLog> {
  return apiFetch(`/fuel-logs/${id}`, { method: "PATCH", body: JSON.stringify(input) });
}

export function deleteFuelLog(id: string): Promise<void> {
  return apiFetch(`/fuel-logs/${id}`, { method: "DELETE" });
}

export interface BulkImportResult {
  imported: number;
  errors: number;
  // One entry per failed row, in the same order the rows were submitted --
  // lets the UI say *which* rows need fixing, not just how many failed.
  errorDetails: string[];
}

export async function createFuelLogsBulk(logs: CreateFuelLogRequest[]): Promise<BulkImportResult> {
  if (logs.length === 0) return { imported: 0, errors: 0, errorDetails: [] };
  // One request for the whole batch instead of N sequential POSTs (Vikunja
  // #39) -- each row gets its own server-side SAVEPOINT, so one bad row
  // doesn't roll back the rest.
  const results = await apiFetch<Array<{ index: number; status: "created" | "error"; error?: string }>>(
    "/fuel-logs/bulk",
    { method: "POST", body: JSON.stringify({ items: logs }) },
  );
  const errorDetails = results.filter((r) => r.status === "error").map((r) => r.error ?? "Unknown error");
  return { imported: results.length - errorDetails.length, errors: errorDetails.length, errorDetails };
}
