// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

// The web record form keeps the same structured fields per category as the mobile apps
// (RecordStructuredFields.kt). Run with `npm test`.

import assert from "node:assert/strict";
import { test } from "node:test";
import { brandLabel, filterLabel, structuredFieldsFor } from "./recordStructuredFields.ts";

const typed = { filter_part_number: " FF-42 ", fluid_type: "AW32", capacity: "2 qt", brand: "WIX" };

test("a fuel filter keeps its part number and brand, nothing fluid", () => {
  assert.deepEqual(structuredFieldsFor("fuel_filter", typed), {
    filter_part_number: "FF-42",
    fluid_type: null,
    capacity: null,
    brand: "WIX",
  });
});

test("hydraulic fluid keeps its type and capacity, no filter or brand", () => {
  assert.deepEqual(structuredFieldsFor("hydraulic_fluid", typed), {
    filter_part_number: null,
    fluid_type: "AW32",
    capacity: "2 qt",
    brand: null,
  });
});

test("HVAC and water filters keep which filter and its brand", () => {
  for (const category of ["hvac_filter_change", "water_filter_change"]) {
    const kept = structuredFieldsFor(category, typed);
    assert.equal(kept.filter_part_number, "FF-42");
    assert.equal(kept.brand, "WIX");
    assert.equal(kept.fluid_type, null);
    assert.equal(kept.capacity, null);
  }
  assert.equal(filterLabel("hvac_filter_change"), "HVAC filter size");
  assert.equal(filterLabel("water_filter_change"), "Water filter cartridge");
});

test("vehicle categories are unchanged, and an oil change records the oil's brand", () => {
  assert.deepEqual(structuredFieldsFor("oil_change", typed), {
    filter_part_number: "FF-42",
    fluid_type: null,
    capacity: "2 qt",
    brand: "WIX",
  });
  assert.equal(brandLabel("oil_change"), "Motor oil brand");
  assert.equal(structuredFieldsFor("coolant", typed).fluid_type, "AW32");
  assert.equal(structuredFieldsFor("coolant", typed).filter_part_number, null);
});

test("a category with no structured fields keeps none, and blanks become null", () => {
  assert.deepEqual(structuredFieldsFor("tire_rotation", typed), {
    filter_part_number: null,
    fluid_type: null,
    capacity: null,
    brand: null,
  });
  assert.equal(structuredFieldsFor("fuel_filter", { ...typed, filter_part_number: "  " }).filter_part_number, null);
});
