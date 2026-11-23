// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

// Which of a maintenance record's structured service fields each category keeps.
// The web twin of the mobile apps' RecordStructuredFields (shared/.../domain/
// RecordStructuredFields.kt), set for set, so a field one platform records is never
// shown, then silently dropped, by another. Keep the two in step.
//
// The equipment and property categories reuse the existing columns rather than adding
// new ones: a fuel filter's part number, an HVAC filter's size and a water filter's
// cartridge are all "which filter" (filter_part_number); hydraulic fluid is a
// fluid_type and capacity like any other.

export const FILTER_PART_NUMBER: ReadonlySet<string> = new Set([
  "oil_change",
  "air_filter",
  "transmission_fluid",
  "fuel_filter",
  "hvac_filter_change",
  "water_filter_change",
]);

export const FLUID_TYPE: ReadonlySet<string> = new Set([
  "transmission_fluid",
  "coolant",
  "differential_front",
  "differential_rear",
  "hydraulic_fluid",
]);

export const CAPACITY: ReadonlySet<string> = new Set([
  "oil_change",
  "transmission_fluid",
  "differential_front",
  "differential_rear",
  "hydraulic_fluid",
]);

export const BRAND: ReadonlySet<string> = new Set([
  "oil_change",
  "air_filter",
  "fuel_filter",
  "hvac_filter_change",
  "water_filter_change",
]);

/** What filter_part_number means for this category: an HVAC filter is bought by size,
 * a water filter by cartridge. */
export function filterLabel(category: string): string {
  switch (category) {
    case "oil_change":
      return "Oil filter part #";
    case "air_filter":
      return "Air filter part #";
    case "transmission_fluid":
      return "Transmission filter part #";
    case "fuel_filter":
      return "Fuel filter part #";
    case "hvac_filter_change":
      return "HVAC filter size";
    case "water_filter_change":
      return "Water filter cartridge";
    default:
      return "Filter part number";
  }
}

export function filterPlaceholder(category: string): string | undefined {
  switch (category) {
    case "hvac_filter_change":
      return "e.g. 16x25x1";
    default:
      return undefined;
  }
}

/** Which brand the record's brand is: the oil on an oil change, the filter otherwise. */
export function brandLabel(category: string): string {
  switch (category) {
    case "oil_change":
      return "Motor oil brand";
    case "air_filter":
      return "Air filter brand";
    case "fuel_filter":
      return "Fuel filter brand";
    default:
      return "Filter brand";
  }
}

/** Only what this category keeps -- everything else null, so a value typed before the
 * category changed mid-edit does not persist unseen. Mirrors the apps' save-time gating. */
export function structuredFieldsFor(
  category: string,
  values: { filter_part_number: string; fluid_type: string; capacity: string; brand: string },
): { filter_part_number: string | null; fluid_type: string | null; capacity: string | null; brand: string | null } {
  const keep = (set: ReadonlySet<string>, value: string) => (set.has(category) ? value.trim() || null : null);
  return {
    filter_part_number: keep(FILTER_PART_NUMBER, values.filter_part_number),
    fluid_type: keep(FLUID_TYPE, values.fluid_type),
    capacity: keep(CAPACITY, values.capacity),
    brand: keep(BRAND, values.brand),
  };
}
