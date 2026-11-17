// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

// The mobile apps' CostOfOwnershipTest, CostTrendTest and the core of
// FuelEconomyCalculatorTest, case for case, so the web shows the numbers the
// apps do. Run with `npm test` (Node's built-in runner, Node 22.18+).

import assert from "node:assert/strict";
import { test } from "node:test";
import {
  allTimeAverage,
  costOfOwnership,
  costTrend,
  economyForDisplay,
  effectiveUnitSystem,
  mpgSeries,
  trailingAverage,
  type CostEntry,
  type FuelLogLike,
} from "./costs.ts";

const near = (actual: number | null, expected: number, within: number) => {
  assert.notEqual(actual, null);
  assert.ok(Math.abs(actual! - expected) <= within, `${actual} not within ${within} of ${expected}`);
};

// --- cost of ownership (today 2026-11-13) -------------------------------------

const calc = (o: Partial<Parameters<typeof costOfOwnership>[0]> = {}) =>
  costOfOwnership({
    purchaseCost: 20_000,
    purchaseDate: "2022-11-13",
    maintenance: 3_000,
    fuel: 7_000,
    status: "active",
    salePrice: null,
    saleDate: null,
    today: "2026-11-13",
    ...o,
  });

test("total includes purchase, maintenance and fuel", () => {
  const c = calc();
  assert.equal(c.purchaseKnown, true);
  assert.equal(c.purchase, 20_000);
  assert.equal(c.total, 30_000);
});

test("per year spreads the total over the years owned", () => {
  const c = calc();
  near(c.yearsOwned, 4, 0.01);
  near(c.perYear, 7_500, 25);
});

test("missing purchase price counts as zero and is flagged", () => {
  const c = calc({ purchaseCost: null });
  assert.equal(c.purchaseKnown, false);
  assert.equal(c.total, 10_000);
});

test("zero purchase price is known; a decimal string from the API works", () => {
  assert.equal(calc({ purchaseCost: 0 }).purchaseKnown, true);
  assert.equal(calc({ purchaseCost: "20000.00" }).total, 30_000);
});

test("negative or non-finite purchase is ignored", () => {
  assert.equal(calc({ purchaseCost: -5 }).purchaseKnown, false);
  assert.equal(calc({ purchaseCost: Number.NaN }).purchaseKnown, false);
  assert.equal(calc({ purchaseCost: Number.NaN }).total, 10_000);
});

test("per year: none in the first year, starts at exactly one year", () => {
  assert.notEqual(calc({ purchaseDate: "2026-09-13" }).yearsOwned, null);
  assert.equal(calc({ purchaseDate: "2026-09-13" }).perYear, null);
  assert.notEqual(calc({ purchaseDate: "2025-11-13" }).perYear, null);
});

test("no per year without a usable date; timestamps are accepted", () => {
  assert.equal(calc({ purchaseDate: null }).perYear, null);
  assert.equal(calc({ purchaseDate: "" }).yearsOwned, null);
  assert.equal(calc({ purchaseDate: "sometime in 2019" }).yearsOwned, null);
  assert.notEqual(calc({ purchaseDate: "2022-11-13T09:30:00Z" }).perYear, null);
});

test("future purchase date has no years owned", () => {
  const c = calc({ purchaseDate: "2027-01-01" });
  assert.equal(c.yearsOwned, null);
  assert.equal(c.perYear, null);
});

test("retired without a sale date has no per year; nothing logged gives zero", () => {
  assert.equal(calc({ status: "archived" }).total, 30_000);
  assert.equal(calc({ status: "archived" }).perYear, null);
  const empty = calc({ purchaseCost: null, maintenance: 0, fuel: 0 });
  assert.equal(empty.total, 0);
  assert.equal(empty.perYear, null);
});

test("a sale is netted out; no sale means net equals total", () => {
  const c = calc({ status: "archived", salePrice: 8_000, saleDate: "2026-11-13" });
  assert.equal(c.saleKnown, true);
  assert.equal(c.netCost, 22_000);
  assert.equal(calc().netCost, calc().total);
});

test("per year stops at the sale date", () => {
  const c = calc({ status: "archived", salePrice: 10_000, saleDate: "2024-11-13" });
  near(c.yearsOwned, 2, 0.01);
  near(c.perYear, 10_000, 10);
  assert.notEqual(calc({ status: "archived", salePrice: 1, saleDate: "2025-11-13" }).perYear, null);
  assert.equal(
    calc({ purchaseDate: "2026-01-01", status: "archived", salePrice: 1, saleDate: "2026-06-01" }).perYear,
    null,
  );
});

test("sale date before purchase is ignored", () => {
  near(calc({ salePrice: 1, saleDate: "2020-01-01" }).yearsOwned, 4, 0.01);
});

test("sold for more than everything spent: negative net, no per year", () => {
  const c = calc({ status: "archived", salePrice: 40_000, saleDate: "2026-11-13" });
  assert.equal(c.netCost, -10_000);
  assert.equal(c.perYear, null);
});

test("zero sale price is known; bad sums are clamped to zero", () => {
  const z = calc({ status: "archived", salePrice: 0, saleDate: "2026-11-13" });
  assert.equal(z.saleKnown, true);
  assert.equal(z.netCost, z.total);
  const b = calc({ maintenance: Number.NaN, fuel: -10 });
  assert.equal(b.maintenance, 0);
  assert.equal(b.fuel, 0);
  assert.equal(b.total, 20_000);
});

// --- cost trend (today 2026-11-14) --------------------------------------------

const TODAY = "2026-11-14";
const e = (performedAt: string, amount: CostEntry["amount"]): CostEntry => ({ performedAt, amount });

test("last three months has three bars, empty ones included", () => {
  const t = costTrend([e("2026-09-03", 120), e("2026-11-01", 80)], [e("2026-11-10T08:00:00Z", 45.5)], 3, TODAY);
  assert.deepEqual(
    t.periods.map((p) => p.start),
    ["2026-09-01", "2026-10-01", "2026-11-01"],
  );
  assert.deepEqual(
    t.periods.map((p) => p.service),
    [120, 0, 80],
  );
  assert.deepEqual(
    t.periods.map((p) => p.fuel),
    [0, 0, 45.5],
  );
  assert.equal(t.periods.at(-1)!.label, "Nov 2026");
  assert.equal(t.periods.at(-1)!.shortLabel, "Nov");
  assert.equal(t.yearly, false);
});

test("spending before the range is left out of its totals", () => {
  const t = costTrend(
    [e("2026-01-15", 500), e("2026-10-15", 100)],
    [e("2025-12-31", 60), e("2026-10-20", 40)],
    6,
    TODAY,
  );
  assert.equal(t.periods.length, 6);
  assert.equal(t.serviceTotal, 100);
  assert.equal(t.fuelTotal, 40);
});

test("all time starts at the first entry", () => {
  const t = costTrend([e("2026-07-02", 10)], [e("2026-08-02", 20)], null, TODAY);
  assert.equal(t.periods[0].start, "2026-07-01");
  assert.equal(t.periods.at(-1)!.start, "2026-11-01");
  assert.equal(t.periods.length, 5);
});

test("long histories become yearly bars", () => {
  const t = costTrend(
    [e("2019-05-01", 300), e("2019-09-01", 200), e("2026-02-01", 50)],
    [e("2023-03-03", 70)],
    null,
    TODAY,
  );
  assert.equal(t.yearly, true);
  assert.deepEqual(
    t.periods.map((p) => p.start),
    [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026].map((y) => `${y}-01-01`),
  );
  assert.equal(t.periods[0].service, 500);
  assert.equal(t.periods[0].label, "2019");
  assert.equal(t.periods.find((p) => p.start === "2023-01-01")!.fuel, 70);
  assert.equal(t.serviceTotal + t.fuelTotal, 620);
});

test("missing, zero, negative and undated amounts are ignored", () => {
  const t = costTrend(
    [e("2026-11-01", null), e("2026-11-01", 0), e("2026-11-01", -5), e("not a date", 99)],
    [e("2026-11-02", Number.NaN), e("", 10)],
    null,
    TODAY,
  );
  assert.equal(t.periods.length, 0);
});

test("no entries with a fixed range still gives empty bars; future entries extend it", () => {
  const empty = costTrend([], [], 12, TODAY);
  assert.equal(empty.periods.length, 12);
  assert.equal(empty.periods[0].start, "2025-12-01");
  const future = costTrend([e("2027-01-05", 25)], [], 3, TODAY);
  assert.equal(future.periods.at(-1)!.start, "2027-01-01");
  assert.equal(future.serviceTotal, 25);
});

test("decimal-string amounts from the API are summed", () => {
  assert.equal(costTrend([e("2026-11-01", "19.99"), e("2026-11-02", "0.01")], [], 1, TODAY).serviceTotal, 20);
});

// --- fuel economy ---------------------------------------------------------------

let n = 0;
const log = (date: string, odometer: number | null, gallons: number | string | null, full = true): FuelLogLike => ({
  id: `log-${++n}`,
  performed_at: date,
  odometer_reading: odometer,
  gallons,
  is_fill_up: full,
});

test("mpg is distance between full fill-ups over the fuel added", () => {
  const points = mpgSeries([log("2026-01-01", 1000, 10), log("2026-01-08", 1300, 10), log("2026-01-15", 1550, "10.000")]);
  assert.deepEqual(
    points.map((p) => p.mpg),
    [30, 25],
  );
});

test("partial fill-ups accumulate into the next full one", () => {
  const points = mpgSeries([log("2026-01-01", 1000, 10), log("2026-01-05", 1150, 5, false), log("2026-01-08", 1300, 5)]);
  assert.deepEqual(
    points.map((p) => p.mpg),
    [30],
  );
});

test("an unknown volume skips its interval and the next starts clean", () => {
  const points = mpgSeries([
    log("2026-01-01", 1000, 10),
    log("2026-01-05", 1150, null, false),
    log("2026-01-08", 1300, 5),
    log("2026-01-15", 1600, 10),
  ]);
  assert.deepEqual(
    points.map((p) => p.mpg),
    [30],
  );
});

test("logs without an odometer are skipped; order is by date", () => {
  const points = mpgSeries([log("2026-01-08", 1300, 10), log("2026-01-04", null, 3), log("2026-01-01", 1000, 10)]);
  assert.deepEqual(
    points.map((p) => p.mpg),
    [30],
  );
});

test("averages: last five and all time", () => {
  const pts = [10, 20, 30, 40, 50, 60].map((mpg, i) => ({ fuelLogId: `${i}`, performedAt: "", odometerReading: i, mpg }));
  assert.equal(trailingAverage(pts), 40);
  assert.equal(allTimeAverage(pts), 35);
  assert.equal(trailingAverage([]), null);
});

test("units: asset beats household beats imperial; metric shows km/L", () => {
  assert.equal(effectiveUnitSystem("metric", "imperial"), "metric");
  assert.equal(effectiveUnitSystem(null, "metric"), "metric");
  assert.equal(effectiveUnitSystem(undefined, undefined), "imperial");
  near(economyForDisplay(30, "metric"), 12.754, 0.001);
  assert.equal(economyForDisplay(30, "imperial"), 30);
});
