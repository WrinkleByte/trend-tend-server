// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

// What a fill-up's reading is: a vehicle's odometer, or a piece of equipment's hour meter
// unless that equipment is set to record an odometer instead (equipment_details.
// fuel_reading_unit). The web twin of the apps' FuelLogReading (shared/.../domain/
// FuelLogReading.kt); keep the two in step. The reading lives in odometer_reading either way.

import type { Asset } from "../../api/types";

type AssetLike = Pick<Asset, "asset_type" | "equipment_details">;

/** Anything but "odometer" is hours, so a value from a newer app reads safely here. */
export function fuelReadingIsHours(asset: AssetLike): boolean {
  return asset.asset_type === "equipment" && asset.equipment_details?.fuel_reading_unit !== "odometer";
}

export function fuelReadingLabel(asset: AssetLike): string {
  return fuelReadingIsHours(asset) ? "Hours" : "Odometer";
}

/** MPG means nothing for an hour-meter reading. */
export function fuelTracksEconomy(asset: AssetLike): boolean {
  return !fuelReadingIsHours(asset);
}

/** Whether fill-up readings count toward an hour-based figure (running cost per hour):
 * only when they are hours. An equipment set to odometer still counts its fuel's cost. */
export function fuelReadingCountsAsHours(asset: AssetLike): boolean {
  return asset.asset_type !== "equipment" || fuelReadingIsHours(asset);
}
