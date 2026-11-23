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
  o: { gallons?: number | null; perGallon?: number | null; total?: number | null; brand?: string } = {},
): FillUpPoint => ({
  performedAt,
  latitude,
  longitude,
  gallons: o.gallons === undefined ? 10 : o.gallons,
  costPerGallon: o.perGallon ?? null,
  totalCost: o.total ?? null,
  gasBrand: o.brand ?? null,
});

test("visits to one place share a pin; most recent first", () => {
  const places = fillUpPlaces([
    p("2026-01-01", 42.123, -71.456, { perGallon: 3.0 }),
    p("2026-03-01T08:00:00Z", 42.1231, -71.4559, { perGallon: 3.4 }),
    p("2026-02-01", 42.2, -71.456, { perGallon: 3.1 }),
  ]);
  assert.equal(places.length, 2);
  // Equal visit counts: the pin goes where you were most recently.
  const home = places.find((x) => x.latitude === 42.1231)!;
  assert.equal(home.visits, 2);
  assert.equal(home.lastVisit, "2026-03-01");
  assert.equal(home.lastPricePerGallon, 3.4);
  assert.ok(Math.abs(home.averagePricePerGallon! - 3.2) < 1e-9);
  assert.equal(places[0].latitude, 42.1231);
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

// The Sunoco at Lynn St and Lynnfield St, Peabody MA: its canopy is at 42.5175, -70.9437,
// and the old 0.001 degree grid drew it at 42.518, -70.944, across Lynnfield St.
test("a pin is drawn where it was saved, not on a grid", () => {
  const [place] = fillUpPlaces([p("2026-11-22", 42.5175, -70.9437)]);
  assert.equal(place.latitude, 42.5175);
  assert.equal(place.longitude, -70.9437);
});

test("other pumps and rounded saves at one station are one place", () => {
  const places = fillUpPlaces([
    p("2026-10-13", 42.5175, -70.9437),
    p("2026-11-22", 42.5175, -70.9437),
    p("2026-12-01", 42.518, -70.944),
    p("2026-12-08", 42.517, -70.944),
    p("2026-12-15", 42.51762, -70.94381),
  ]);
  assert.equal(places.length, 1);
  assert.equal(places[0].visits, 5);
  assert.equal(places[0].latitude, 42.5175);
  assert.equal(places[0].longitude, -70.9437);
});

test("stations a street apart with different brands stay separate", () => {
  const places = fillUpPlaces([
    p("2026-01-01", 42.5175, -70.9437, { brand: "Sunoco" }),
    p("2026-01-05", 42.5175, -70.9437, { brand: "Sunoco" }),
    p("2026-01-08", 42.5179, -70.9431, { brand: "Shell" }),
    p("2026-01-15", 42.51752, -70.94368),
    p("2026-01-22", 42.51749, -70.94372, { brand: " sunoco " }),
  ]);
  assert.equal(places.length, 2);
  assert.equal(places.find((x) => x.latitude === 42.5175)!.visits, 4);
  assert.equal(places.find((x) => x.latitude === 42.5179)!.visits, 1);
});

test("places farther apart than a station are separate", () => {
  const places = fillUpPlaces([p("2026-01-01", 42.5175, -70.9437), p("2026-01-02", 42.5186, -70.9437)]);
  assert.equal(places.length, 2);
});

test("the order the rows came in does not matter", () => {
  const rows = [
    p("2026-01-01", 42.5175, -70.9437),
    p("2026-01-02", 42.518, -70.944),
    p("2026-01-03", 42.5185, -70.9443),
    p("2026-01-04", 42.5175, -70.9437),
  ];
  const key = (xs: ReturnType<typeof fillUpPlaces>) => JSON.stringify([...xs].sort((a, b) => a.latitude - b.latitude));
  assert.equal(key(fillUpPlaces(rows)), key(fillUpPlaces([...rows].reverse())));
});
