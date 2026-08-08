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

export async function createFuelLogsBulk(
  logs: CreateFuelLogRequest[],
): Promise<{ imported: number; errors: number }> {
  let imported = 0;
  let errors = 0;

  for (const log of logs) {
    try {
      await createFuelLog(log);
      imported++;
    } catch (error) {
      errors++;
      console.error("Failed to import fuel log:", error);
    }
  }

  return { imported, errors };
}
