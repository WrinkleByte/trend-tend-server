// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import assert from "node:assert/strict";
import { test } from "node:test";
import { fuelReadingCountsAsHours, fuelReadingIsHours, fuelReadingLabel, fuelTracksEconomy } from "./fuelReading.ts";

const equipment = (fuel_reading_unit?: string | null) =>
  ({ asset_type: "equipment", equipment_details: { fuel_reading_unit } }) as never;

test("equipment records hours by default, with no MPG", () => {
  for (const unit of [undefined, null, "hours", "something-newer"]) {
    assert.equal(fuelReadingIsHours(equipment(unit)), true);
    assert.equal(fuelReadingLabel(equipment(unit)), "Hours");
    assert.equal(fuelTracksEconomy(equipment(unit)), false);
  }
});

test("equipment set to odometer records a distance with MPG, kept out of hours", () => {
  assert.equal(fuelReadingLabel(equipment("odometer")), "Odometer");
  assert.equal(fuelTracksEconomy(equipment("odometer")), true);
  assert.equal(fuelReadingCountsAsHours(equipment("odometer")), false);
  assert.equal(fuelReadingCountsAsHours(equipment("hours")), true);
});

test("a vehicle is always an odometer", () => {
  const vehicle = { asset_type: "vehicle", equipment_details: null } as never;
  assert.equal(fuelReadingLabel(vehicle), "Odometer");
  assert.equal(fuelTracksEconomy(vehicle), true);
});
