import { apiFetch } from "./client";
import type { CreateTripLogRequest, TripLog } from "./types";

export function listTripLogs(assetId?: string): Promise<TripLog[]> {
  const query = assetId ? `?asset_id=${encodeURIComponent(assetId)}` : "";
  return apiFetch(`/trip-logs${query}`);
}

export function getTripLog(id: string): Promise<TripLog> {
  return apiFetch(`/trip-logs/${id}`);
}

export function createTripLog(input: CreateTripLogRequest): Promise<TripLog> {
  return apiFetch("/trip-logs", { method: "POST", body: JSON.stringify(input) });
}

export function updateTripLog(id: string, input: Partial<CreateTripLogRequest>): Promise<TripLog> {
  return apiFetch(`/trip-logs/${id}`, { method: "PATCH", body: JSON.stringify(input) });
}

export function deleteTripLog(id: string): Promise<void> {
  return apiFetch(`/trip-logs/${id}`, { method: "DELETE" });
}
