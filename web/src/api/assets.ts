import { apiFetch } from "./client";
import type { Asset, AssetCreateInput } from "./types";

export function listAssets(): Promise<Asset[]> {
  return apiFetch("/assets");
}

export function getAsset(id: string): Promise<Asset> {
  return apiFetch(`/assets/${id}`);
}

export function createAsset(input: AssetCreateInput): Promise<Asset> {
  return apiFetch("/assets", { method: "POST", body: JSON.stringify(input) });
}

export function updateAsset(id: string, input: Partial<AssetCreateInput>): Promise<Asset> {
  return apiFetch(`/assets/${id}`, { method: "PATCH", body: JSON.stringify(input) });
}

export function deleteAsset(id: string): Promise<void> {
  return apiFetch(`/assets/${id}`, { method: "DELETE" });
}
