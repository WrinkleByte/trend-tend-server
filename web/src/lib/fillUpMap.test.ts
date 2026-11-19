// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

// The apps' FillUpMapTest, case for case.

import assert from "node:assert/strict";
import { test } from "node:test";
import { fillUpPlaces, pricePerGallon, type FillUpPoint } from "./fillUpMap.ts";

const p = (
  performedAt: string,
  latitude: number | null,
  longitude: number | null,
  o: { gallons?: number | null; perGallon?: number | null; total?: number | null } = {},
): FillUpPoint => ({
  performedAt,
  latitude,
  longitude,
  gallons: o.gallons === undefined ? 10 : o.gallons,
  costPerGallon: o.perGallon ?? null,
  totalCost: o.total ?? null,
});

test("visits to one place share a pin; most recent first", () => {
  const places = fillUpPlaces([
    p("2026-01-01", 42.123, -71.456, { perGallon: 3.0 }),
    p("2026-03-01T08:00:00Z", 42.1231, -71.4559, { perGallon: 3.4 }),
    p("2026-02-01", 42.2, -71.456, { perGallon: 3.1 }),
  ]);
  assert.equal(places.length, 2);
  const home = places.find((x) => x.latitude === 42.123)!;
  assert.equal(home.visits, 2);
  assert.equal(home.lastVisit, "2026-03-01");
  assert.equal(home.lastPricePerGallon, 3.4);
  assert.ok(Math.abs(home.averagePricePerGallon! - 3.2) < 1e-9);
  assert.equal(places[0].latitude, 42.123);
});

test("average is weighted by gallons", () => {
  const [place] = fillUpPlaces([
    p("2026-01-01", 1, 1, { gallons: 15, perGallon: 3 }),
    p("2026-02-01", 1, 1, { gallons: 5, perGallon: 4 }),
  ]);
  assert.ok(Math.abs(place.averagePricePerGallon! - 3.25) < 1e-9);
});

test("price falls back to total over gallons", () => {
  assert.equal(pricePerGallon(p("2026-01-01", 1, 1, { gallons: 10, total: 35 })), 3.5);
  assert.equal(pricePerGallon(p("2026-01-01", 1, 1, { gallons: null, total: 35 })), null);
  const [place] = fillUpPlaces([p("2026-01-01", 1, 1, { gallons: null, total: 35 })]);
  assert.equal(place.lastPricePerGallon, null);
  assert.equal(place.averagePricePerGallon, null);
  assert.equal(place.visits, 1);
});

test("fill-ups without usable coordinates are left off; API decimal strings work", () => {
  assert.equal(
    fillUpPlaces([p("2026-01-01", null, -71), p("2026-01-01", 42, null), p("2026-01-01", 0, 0), p("2026-01-01", 95, 10), p("2026-01-01", Number.NaN, 10)])
      .length,
    0,
  );
  const [place] = fillUpPlaces([{ performedAt: "2026-01-01", latitude: "42.123000", longitude: "-71.456000", gallons: "10.000", costPerGallon: "3.299", totalCost: null }]);
  assert.equal(place.latitude, 42.123);
  assert.equal(place.lastPricePerGallon, 3.299);
});
