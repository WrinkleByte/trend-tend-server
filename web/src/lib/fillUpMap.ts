// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Fill-ups grouped into places for the fill-up map (Vikunja #100): the web
 * port of the apps' shared FillUpMap.places, same rules and tests
 * (fillUpMap.test.ts). Only the household's own fill-ups: no station search,
 * no live prices.
 */

export interface FillUpPoint {
  performedAt: string;
  latitude: number | string | null | undefined;
  longitude: number | string | null | undefined;
  gallons: number | string | null | undefined;
  costPerGallon: number | string | null | undefined;
  totalCost: number | string | null | undefined;
}

export interface FillUpPlace {
  latitude: number;
  longitude: number;
  visits: number;
  /** Most recent visit, YYYY-MM-DD. */
  lastVisit: string;
  lastPricePerGallon: number | null;
  /** Weighted by gallons when every priced visit has them, else a plain mean. */
  averagePricePerGallon: number | null;
}

const num = (v: number | string | null | undefined): number | null => {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};
const positive = (v: number | string | null | undefined): number | null => {
  const n = num(v);
  return n != null && n > 0 ? n : null;
};

/** The recorded price per gallon, else total cost over gallons. */
export function pricePerGallon(p: FillUpPoint): number | null {
  const recorded = positive(p.costPerGallon);
  if (recorded != null) return recorded;
  const total = positive(p.totalCost);
  const gallons = positive(p.gallons);
  return total != null && gallons != null ? total / gallons : null;
}

/** Same 0.001° grid as the apps' LocationPrivacy (about 110 m). */
const grid = (v: number) => Math.round(v * 1000) / 1000;

export function fillUpPlaces(points: FillUpPoint[]): FillUpPlace[] {
  const groups = new Map<string, { lat: number; lon: number; visits: FillUpPoint[] }>();
  for (const p of points) {
    const lat = num(p.latitude);
    const lon = num(p.longitude);
    if (lat == null || lon == null || lat < -90 || lat > 90 || lon < -180 || lon > 180) continue;
    if (lat === 0 && lon === 0) continue;
    const key = `${grid(lat)},${grid(lon)}`;
    if (!groups.has(key)) groups.set(key, { lat: grid(lat), lon: grid(lon), visits: [] });
    groups.get(key)!.visits.push(p);
  }
  const places: FillUpPlace[] = [];
  for (const g of groups.values()) {
    const visits = [...g.visits].sort((a, b) => (a.performedAt < b.performedAt ? -1 : a.performedAt > b.performedAt ? 1 : 0));
    const priced = visits.flatMap((v) => {
      const price = pricePerGallon(v);
      return price == null ? [] : [{ v, price }];
    });
    const weighted = priced.every(({ v }) => positive(v.gallons) != null);
    let average: number | null = null;
    if (priced.length > 0) {
      average = weighted
        ? priced.reduce((s, { v, price }) => s + price * positive(v.gallons)!, 0) /
          priced.reduce((s, { v }) => s + positive(v.gallons)!, 0)
        : priced.reduce((s, { price }) => s + price, 0) / priced.length;
    }
    places.push({
      latitude: g.lat,
      longitude: g.lon,
      visits: visits.length,
      lastVisit: visits[visits.length - 1].performedAt.slice(0, 10),
      lastPricePerGallon: priced.length ? priced[priced.length - 1].price : null,
      averagePricePerGallon: average,
    });
  }
  return places.sort((a, b) => (a.lastVisit < b.lastVisit ? 1 : a.lastVisit > b.lastVisit ? -1 : 0));
}
