// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { apiFetch } from "./client";
import type { Asset, AssetCreateInput } from "./types";

/** `mineOnly` is a view filter, not access control — the backend still
 *  returns unassigned assets under it, and every member can read everything
 *  either way. */
export function listAssets(mineOnly = false): Promise<Asset[]> {
  return apiFetch(mineOnly ? "/assets?mine_only=true" : "/assets");
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
