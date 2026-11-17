// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Cost Trends, cost of ownership and fuel economy for one asset: the web
 * side of the mobile apps' shared calculations, ported rule for rule so
 * every platform shows the same numbers for the same data. The Kotlin
 * originals, which are the reference (tendfida-mobile, shared module):
 *
 * - CostOfOwnershipCalculator.compute  -> costOfOwnership()
 * - CostTrendCalculator.compute        -> costTrend()
 * - FuelEconomyCalculator              -> mpgSeries(), trailingAverage(), allTimeAverage()
 *
 * Tested in costs.test.ts against the same cases as the Kotlin tests.
 * Dates are plain "YYYY-MM-DD" calendar days, never Date objects, so no
 * time zone can shift a record into the neighbouring month.
 */

// --- calendar days ----------------------------------------------------------

/** A calendar day; month is 1-12. */
interface Day {
  y: number;
  m: number;
  d: number;
}

function parseDay(value: string | null | undefined): Day | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec((value ?? "").trim());
  if (!match) return null;
  const [y, m, d] = [Number(match[1]), Number(match[2]), Number(match[3])];
  if (m < 1 || m > 12 || d < 1 || d > daysInMonth(y, m)) return null;
  return { y, m, d };
}

function daysInMonth(y: number, m: number): number {
  return new Date(Date.UTC(y, m, 0)).getUTCDate();
}

function dayNumber(day: Day): number {
  return Math.round(Date.UTC(day.y, day.m - 1, day.d) / 86_400_000);
}

function compareDays(a: Day, b: Day): number {
  return a.y - b.y || a.m - b.m || a.d - b.d;
}

/** Same rule as kotlinx-datetime's plus(1, YEAR): Feb 29 becomes Feb 28. */
function plusOneYear(day: Day): Day {
  return { y: day.y + 1, m: day.m, d: Math.min(day.d, daysInMonth(day.y + 1, day.m)) };
}

function iso(day: Day): string {
  return `${day.y}-${String(day.m).padStart(2, "0")}-${String(day.d).padStart(2, "0")}`;
}

/** Today in the viewer's own time zone. */
export function todayIso(): string {
  const now = new Date();
  return iso({ y: now.getFullYear(), m: now.getMonth() + 1, d: now.getDate() });
}

// --- cost of ownership ------------------------------------------------------

export interface CostOfOwnership {
  purchase: number;
  purchaseKnown: boolean;
  maintenance: number;
  fuel: number;
  /** Purchase + maintenance + fuel: everything spent. */
  total: number;
  /** What it sold for; 0 when not sold or not recorded. */
  sale: number;
  saleKnown: boolean;
  /** total less sale: what owning it actually cost. Negative if it sold for more than everything spent. */
  netCost: number;
  /** Years from purchase to sale (or to today if unsold), fractional; null without a usable purchase date. */
  yearsOwned: number | null;
  /** netCost per year owned; null until owned a full year, without a purchase date, when it cost nothing net,
   * or when retired with no sale date (nothing to stop the clock at). */
  perYear: number | null;
}

const DAYS_PER_YEAR = 365.25;

function amount(value: number | string | null | undefined): number | null {
  if (value == null || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

export function costOfOwnership(input: {
  purchaseCost: number | string | null | undefined;
  purchaseDate: string | null | undefined;
  maintenance: number;
  fuel: number;
  status: string;
  salePrice: number | string | null | undefined;
  saleDate: string | null | undefined;
  today: string;
}): CostOfOwnership {
  const purchaseAmount = amount(input.purchaseCost);
  const saleAmount = amount(input.salePrice);
  const purchase = purchaseAmount ?? 0;
  const sale = saleAmount ?? 0;
  const m = Number.isFinite(input.maintenance) && input.maintenance > 0 ? input.maintenance : 0;
  const f = Number.isFinite(input.fuel) && input.fuel > 0 ? input.fuel : 0;
  const total = purchase + m + f;
  const net = total - sale;

  const bought = parseDay(input.purchaseDate);
  const sold = parseDay(input.saleDate);
  const today = parseDay(input.today)!;
  // The clock stops at the sale. A sale date before the purchase date is a
  // typo, so it's ignored rather than giving negative years.
  const end = sold && (!bought || compareDays(sold, bought) >= 0) ? sold : today;
  const days = bought ? dayNumber(end) - dayNumber(bought) : null;
  const years = days != null && days >= 0 ? days / DAYS_PER_YEAR : null;
  // Retired without a sale date: no end to measure to.
  const clockStops = input.status === "active" || sold != null;
  const perYear =
    years != null && bought && compareDays(plusOneYear(bought), end) <= 0 && clockStops && net > 0 ? net / years : null;

  return {
    purchase,
    purchaseKnown: purchaseAmount != null,
    maintenance: m,
    fuel: f,
    total,
    sale,
    saleKnown: saleAmount != null,
    netCost: net,
    yearsOwned: years,
    perYear,
  };
}

// --- cost trend --------------------------------------------------------------

/** One dated amount: a service record's cost or a fuel log's total. */
export interface CostEntry {
  performedAt: string;
  amount: number | string | null | undefined;
}

export interface CostPeriod {
  /** First day of the month or year, YYYY-MM-DD. */
  start: string;
  /** "Nov 2026", or "2026" for a year. */
  label: string;
  /** "Nov", or "2026" for a year: for axis ticks. */
  shortLabel: string;
  service: number;
  fuel: number;
}

export interface CostTrend {
  /** Oldest first, every month (or year) in the range, zeros included. */
  periods: CostPeriod[];
  /** True when periods are calendar years. */
  yearly: boolean;
  serviceTotal: number;
  fuelTotal: number;
}

/** Past this many months, "All" switches from monthly to yearly bars. */
export const MAX_MONTHLY_BARS = 36;

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Month index counted from year 0, for stepping through months. */
function monthIndex(day: Day): number {
  return day.y * 12 + (day.m - 1);
}

function fromMonthIndex(index: number): Day {
  return { y: Math.floor(index / 12), m: (index % 12) + 1, d: 1 };
}

function dated(entries: CostEntry[]): { month: number; amount: number }[] {
  const out: { month: number; amount: number }[] = [];
  for (const entry of entries) {
    const n = Number(entry.amount);
    if (entry.amount == null || entry.amount === "" || !Number.isFinite(n) || n <= 0) continue;
    const day = parseDay(entry.performedAt);
    if (!day) continue;
    out.push({ month: monthIndex(day), amount: n });
  }
  return out;
}

/**
 * monthsBack null means everything logged. Otherwise the range is the last
 * monthsBack calendar months up to and including today's.
 */
export function costTrend(service: CostEntry[], fuel: CostEntry[], monthsBack: number | null, today: string): CostTrend {
  const s = dated(service);
  const f = dated(fuel);
  const all = [...s, ...f];
  const thisMonth = monthIndex(parseDay(today)!);
  const latest = Math.max(thisMonth, ...all.map((e) => e.month));

  let from: number;
  let yearly: boolean;
  if (monthsBack != null) {
    from = thisMonth - (Math.max(monthsBack, 1) - 1);
    yearly = false;
  } else {
    if (all.length === 0) return { periods: [], yearly: false, serviceTotal: 0, fuelTotal: 0 };
    const earliest = Math.min(...all.map((e) => e.month));
    yearly = latest - earliest + 1 > MAX_MONTHLY_BARS;
    from = yearly ? Math.floor(earliest / 12) * 12 : earliest;
  }

  const periods: CostPeriod[] = [];
  for (let cursor = from; cursor <= latest; cursor += yearly ? 12 : 1) {
    const next = cursor + (yearly ? 12 : 1);
    const inBucket = (e: { month: number }) => e.month >= cursor && e.month < next;
    const start = fromMonthIndex(cursor);
    periods.push({
      start: iso(start),
      label: yearly ? `${start.y}` : `${MONTHS[start.m - 1]} ${start.y}`,
      shortLabel: yearly ? `${start.y}` : MONTHS[start.m - 1],
      service: s.filter(inBucket).reduce((sum, e) => sum + e.amount, 0),
      fuel: f.filter(inBucket).reduce((sum, e) => sum + e.amount, 0),
    });
  }
  return {
    periods,
    yearly,
    serviceTotal: periods.reduce((sum, p) => sum + p.service, 0),
    fuelTotal: periods.reduce((sum, p) => sum + p.fuel, 0),
  };
}

// --- fuel economy -------------------------------------------------------------

export interface FuelLogLike {
  id: string;
  performed_at: string;
  odometer_reading: number | null;
  gallons: number | string | null;
  is_fill_up: boolean;
}

export interface MpgPoint {
  fuelLogId: string;
  performedAt: string;
  odometerReading: number;
  mpg: number;
}

/** Full-to-full intervals: distance between two full fill-ups over all the fuel added in between. */
export function mpgSeries(logs: FuelLogLike[]): MpgPoint[] {
  const sorted = logs
    .filter((l) => l.odometer_reading != null)
    .sort((a, b) =>
      a.performed_at < b.performed_at ? -1 : a.performed_at > b.performed_at ? 1 : a.odometer_reading! - b.odometer_reading!,
    );
  const points: MpgPoint[] = [];
  let gallonsSoFar = 0;
  // A fill-up with no recorded volume makes its whole interval unusable: the
  // fuel total would be short by an unknown amount and the MPG silently too
  // high. The interval is skipped and the next one starts clean.
  let unknownVolume = false;
  let lastFullOdometer: number | null = null;
  for (const log of sorted) {
    const odometer = log.odometer_reading!;
    const gallons = log.gallons == null || log.gallons === "" ? null : Number(log.gallons);
    if (gallons == null || !Number.isFinite(gallons)) unknownVolume = true;
    else gallonsSoFar += gallons;
    if (log.is_fill_up) {
      if (lastFullOdometer != null && gallonsSoFar > 0 && !unknownVolume) {
        const distance = odometer - lastFullOdometer;
        if (distance > 0) {
          points.push({ fuelLogId: log.id, performedAt: log.performed_at, odometerReading: odometer, mpg: distance / gallonsSoFar });
        }
      }
      lastFullOdometer = odometer;
      gallonsSoFar = 0;
      unknownVolume = false;
    }
  }
  return points;
}

export function trailingAverage(points: MpgPoint[], windowSize = 5): number | null {
  if (points.length === 0) return null;
  const window = points.slice(-windowSize);
  return window.reduce((sum, p) => sum + p.mpg, 0) / window.length;
}

export function allTimeAverage(points: MpgPoint[]): number | null {
  if (points.length === 0) return null;
  return points.reduce((sum, p) => sum + p.mpg, 0) / points.length;
}

// --- units --------------------------------------------------------------------

export type UnitSystem = "imperial" | "metric";

const KM_PER_MILE = 1.609344;
const LITERS_PER_US_GALLON = 3.785411784;

/** The asset's own setting, else the household's, else imperial: as on mobile, minus its per-device preference. */
export function effectiveUnitSystem(assetOverride: string | null | undefined, householdSetting: unknown): UnitSystem {
  const pick = (v: unknown) => (v === "metric" || v === "imperial" ? v : null);
  return pick(assetOverride) ?? pick(householdSetting) ?? "imperial";
}

/** Economy is stored as miles per US gallon; metric shows km/L, as the apps do. */
export function economyForDisplay(mpg: number, system: UnitSystem): number {
  return system === "metric" ? (mpg * KM_PER_MILE) / LITERS_PER_US_GALLON : mpg;
}

export function economyUnitLabel(system: UnitSystem): string {
  return system === "metric" ? "km/L" : "mpg";
}

// --- running cost per mile / hour (Vikunja #131) --------------------------------

/** One logged cost with the odometer (or equipment hours) reading taken with it, if any. */
export interface UsageCostEntry {
  performedAt: string;
  amount: number | string | null | undefined;
  reading: number | null | undefined;
}

export interface RunningCost {
  cost: number;
  /** Miles (as stored) or hours, first reading to latest. */
  usage: number;
  /** Dollars per mile or per hour. */
  perUnit: number;
}

export const MIN_MILES = 500;
export const MIN_HOURS = 10;

/**
 * Service and fuel over the miles or hours logged: the shared Kotlin
 * RunningCostCalculator.compute. Usage runs from the lowest reading (service
 * record, fill-up or the current odometer/hours) to the highest. Cost is
 * every service record and fill-up dated on or after the first reading's
 * date, except the fill-up that took that reading (its fuel was burned
 * before tracking began). Purchase price is left out: nothing records the
 * odometer at purchase. Null under MIN_MILES / MIN_HOURS or with no spending.
 */
export function runningCost(
  service: UsageCostEntry[],
  fuel: UsageCostEntry[],
  currentReading: number | null | undefined,
  isEquipment: boolean,
): RunningCost | null {
  const day = (v: string) => (/^\d{4}-\d{2}-\d{2}/.exec(v.trim())?.[0] ?? null);
  type Reading = { value: number; date: string | null; fuelIndex: number | null };
  const readings: Reading[] = [];
  for (const e of service) if (e.reading != null && e.reading > 0) readings.push({ value: e.reading, date: day(e.performedAt), fuelIndex: null });
  fuel.forEach((e, i) => {
    if (e.reading != null && e.reading > 0) readings.push({ value: e.reading, date: day(e.performedAt), fuelIndex: i });
  });
  if (currentReading != null && currentReading > 0) readings.push({ value: currentReading, date: null, fuelIndex: null });
  if (readings.length === 0) return null;
  // Lowest value first; on a tie a fill-up wins, so its fuel is excluded.
  const first = readings.reduce((a, b) =>
    b.value < a.value || (b.value === a.value && b.fuelIndex != null && a.fuelIndex == null) ? b : a,
  );
  const usage = Math.max(...readings.map((r) => r.value)) - first.value;
  if (usage < (isEquipment ? MIN_HOURS : MIN_MILES)) return null;
  const counts = (e: UsageCostEntry) => first.date == null || (day(e.performedAt) ?? "") >= first.date;
  const positive = (v: UsageCostEntry["amount"]) => {
    const n = Number(v);
    return v != null && v !== "" && Number.isFinite(n) && n > 0 ? n : 0;
  };
  const cost =
    service.filter(counts).reduce((s, e) => s + positive(e.amount), 0) +
    fuel.filter((e, i) => i !== first.fuelIndex && counts(e)).reduce((s, e) => s + positive(e.amount), 0);
  if (cost <= 0) return null;
  return { cost, usage, perUnit: cost / usage };
}

/** Per mile to per kilometre, for metric display. */
export function perKilometre(perMile: number): number {
  return perMile / KM_PER_MILE;
}
