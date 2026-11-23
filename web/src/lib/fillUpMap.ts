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
  /** The station's brand, when recorded: keeps two stations across the street apart. */
  gasBrand?: string | null;
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

/** Far enough to cover a station's pumps plus the apps' ~110 m save-time rounding
 * (LocationPrivacy); under a city block. Same value as the apps' FillUpMap. */
export const SAME_PLACE_METERS = 75;

/** Great-circle distance in meters (haversine). */
export function distanceMeters(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const r = 6_371_000;
  const rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad;
  const dLon = (lon2 - lon1) * rad;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * r * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

interface Spot {
  lat: number;
  lon: number;
  visits: FillUpPoint[];
}

const brandsOf = (spot: Spot): Set<string> =>
  new Set(spot.visits.flatMap((v) => (v.gasBrand && v.gasBrand.trim() ? [v.gasBrand.trim().toLowerCase()] : [])));

/**
 * One pin per place: every fill-up within SAME_PLACE_METERS of it, so another pump, a GPS
 * reading a little off, or a rounded save all count as the same station. Two fill-ups whose
 * recorded brands differ are never one place (stations on opposite corners). The pin sits at
 * the place's most-visited exact coordinate, as saved -- not on a grid, which put a corner
 * station's pin across the street.
 */
export function fillUpPlaces(points: FillUpPoint[]): FillUpPlace[] {
  const bySpot = new Map<string, Spot>();
  for (const p of points) {
    const lat = num(p.latitude);
    const lon = num(p.longitude);
    if (lat == null || lon == null || lat < -90 || lat > 90 || lon < -180 || lon > 180) continue;
    if (lat === 0 && lon === 0) continue;
    const key = `${lat},${lon}`;
    if (!bySpot.has(key)) bySpot.set(key, { lat, lon, visits: [] });
    bySpot.get(key)!.visits.push(p);
  }
  const latest = (s: Spot) => s.visits.reduce((m, v) => (v.performedAt > m ? v.performedAt : m), "");
  // Most-visited first, so a place is anchored where you usually are; ties by most
  // recent visit, then by position, so the result never depends on row order.
  const spots = [...bySpot.values()].sort(
    (a, b) =>
      b.visits.length - a.visits.length ||
      (latest(a) < latest(b) ? 1 : latest(a) > latest(b) ? -1 : 0) ||
      a.lat - b.lat ||
      a.lon - b.lon,
  );

  const clusters: { anchor: Spot; spots: Spot[]; brands: Set<string> }[] = [];
  for (const spot of spots) {
    const spotBrands = brandsOf(spot);
    let home: (typeof clusters)[number] | null = null;
    let best = Infinity;
    for (const c of clusters) {
      const compatible = spotBrands.size === 0 || c.brands.size === 0 || [...c.brands].some((b) => spotBrands.has(b));
      if (!compatible) continue;
      const d = distanceMeters(c.anchor.lat, c.anchor.lon, spot.lat, spot.lon);
      if (d <= SAME_PLACE_METERS && d < best) {
        best = d;
        home = c;
      }
    }
    if (home == null) clusters.push({ anchor: spot, spots: [spot], brands: new Set(spotBrands) });
    else {
      home.spots.push(spot);
      spotBrands.forEach((b) => home!.brands.add(b));
    }
  }

  const places: FillUpPlace[] = [];
  for (const c of clusters) {
    const visits = c.spots
      .flatMap((s) => s.visits)
      .sort((a, b) => (a.performedAt < b.performedAt ? -1 : a.performedAt > b.performedAt ? 1 : 0));
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
      latitude: c.anchor.lat,
      longitude: c.anchor.lon,
      visits: visits.length,
      lastVisit: visits[visits.length - 1].performedAt.slice(0, 10),
      lastPricePerGallon: priced.length ? priced[priced.length - 1].price : null,
      averagePricePerGallon: average,
    });
  }
  return places.sort((a, b) => (a.lastVisit < b.lastVisit ? 1 : a.lastVisit > b.lastVisit ? -1 : 0));
}
