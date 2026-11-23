// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useQuery } from "@tanstack/react-query";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import { getCurrentHousehold } from "../../api/households";
import type { Asset, FuelLog } from "../../api/types";
import { effectiveUnitSystem } from "../../lib/costs";
import { fillUpPlaces, type FillUpPlace } from "../../lib/fillUpMap";
import { formatDate } from "../../lib/format";

const LITERS_PER_US_GALLON = 3.785411784;

/**
 * Where this vehicle has been filled up (Vikunja #100), on OpenStreetMap
 * via Leaflet: one pin per place, with how often and what you paid. The
 * apps show the same pins (Apple Maps on iPhone, OpenStreetMap on Android).
 * Tiles load from tile.openstreetmap.org (allowed in nginx.conf's CSP).
 */
export function FuelMap({ asset, logs }: { asset: Asset; logs: FuelLog[] }) {
  const { data: household } = useQuery({ queryKey: ["household"], queryFn: getCurrentHousehold });
  const metric = effectiveUnitSystem(asset.vehicle_details?.unit_system_override, household?.settings?.unit_system) === "metric";
  const places = fillUpPlaces(
    logs.map((l) => ({
      performedAt: l.performed_at,
      latitude: l.latitude,
      longitude: l.longitude,
      gallons: l.gallons,
      costPerGallon: l.cost_per_gallon,
      totalCost: l.total_cost,
      gasBrand: l.gas_brand,
    })),
  );

  return (
    <section className="fuel-map" aria-labelledby="fuel-map-heading">
      <h2 id="fuel-map-heading">Fill-Up Map</h2>
      {places.length === 0 ? (
        <div className="chart-empty">
          <strong>No Fill-Up Locations Yet</strong>
          <p>Fill-ups logged in the apps with location saving on (Settings) appear here.</p>
        </div>
      ) : (
        <LeafletMap places={places} metric={metric} />
      )}
    </section>
  );
}

function price(perGallon: number | null, metric: boolean): string | null {
  if (perGallon == null) return null;
  const value = metric ? perGallon / LITERS_PER_US_GALLON : perGallon;
  return `$${value.toFixed(2)}/${metric ? "L" : "gal"}`;
}

function LeafletMap({ places, metric }: { places: FillUpPlace[]; metric: boolean }) {
  const element = useRef<HTMLDivElement>(null);
  const key = JSON.stringify(places) + String(metric);

  useEffect(() => {
    if (!element.current) return;
    const map = L.map(element.current, { scrollWheelZoom: false });
    map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      // OpenStreetMap's tile policy requires a Referer from web pages and
      // answers 403 "Access blocked" without one. The site's own policy
      // (nginx.conf: Referrer-Policy same-origin) sends none cross-origin,
      // so the tile requests alone send the origin (never the path).
      referrerPolicy: "strict-origin-when-cross-origin",
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    for (const place of places) {
      // Built from text nodes, not HTML strings.
      const popup = document.createElement("div");
      const line = (text: string, strong = false) => {
        const el = document.createElement(strong ? "strong" : "div");
        el.textContent = text;
        popup.appendChild(el);
      };
      line(`${place.visits} fill-up${place.visits === 1 ? "" : "s"} here`, true);
      const last = price(place.lastPricePerGallon, metric);
      line(`Last: ${formatDate(place.lastVisit)}${last ? ` · ${last}` : ""}`);
      const average = price(place.averagePricePerGallon, metric);
      if (place.visits > 1 && average) line(`Average: ${average}`);
      L.circleMarker([place.latitude, place.longitude], {
        radius: 9,
        color: "#c97f17",
        weight: 2,
        fillColor: "#f2a93b",
        fillOpacity: 0.9,
      })
        .bindPopup(popup)
        .bindTooltip(last ?? "Fill-up")
        .addTo(map);
    }
    if (places.length === 1) {
      map.setView([places[0].latitude, places[0].longitude], 15);
    } else {
      map.fitBounds(L.latLngBounds(places.map((p) => [p.latitude, p.longitude] as [number, number])), { padding: [30, 30] });
    }
    return () => {
      map.off();
      map.remove();
    };
    // Rebuilt only when the places or units change; `key` covers both.
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps

  return <div ref={element} className="fuel-map-canvas" data-testid="fuel-map" role="region" aria-label="Map of fill-up locations" />;
}
