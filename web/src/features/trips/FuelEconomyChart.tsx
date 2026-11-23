// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getCurrentHousehold } from "../../api/households";
import { listFuelLogs } from "../../api/fuelLogs";
import type { Asset, FuelLog } from "../../api/types";
import {
  allTimeAverage,
  economyForDisplay,
  economyUnitLabel,
  effectiveUnitSystem,
  mpgSeries,
  todayIso,
  trailingAverage,
} from "../../lib/costs";
import { formatDate } from "../../lib/format";
import { PeriodPicker } from "../assets/CostsSection";
import { FuelMap } from "./FuelMap";
import { PERIODS, type PeriodKey } from "../assets/useAssetCosts";
import { fuelTracksEconomy } from "./fuelReading";

/** The first day of the month monthsBack-1 months before today's: the same
 * cutoff mobile's Fuel Economy chart uses for its range. */
function cutoff(monthsBack: number): string {
  const [y, m] = todayIso().split("-").map(Number);
  const index = y * 12 + (m - 1) - (monthsBack - 1);
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}-01`;
}

/** The Fuel tab's chart, on the same query (and key) as the fuel log list below it. */
export function FuelEconomyPanel({ asset }: { asset: Asset }) {
  const { data: logs } = useQuery({ queryKey: ["fuel-logs", asset.id], queryFn: () => listFuelLogs(asset.id) });
  if (!logs) return null;
  return (
    <>
      {/* No MPG for an hour-meter reading; the map of where it filled up still applies. */}
      {fuelTracksEconomy(asset) && <FuelEconomyChart asset={asset} logs={logs} />}
      <FuelMap asset={asset} logs={logs} />
    </>
  );
}

/**
 * Fuel economy over time, the mobile apps' Fuel Economy screen: one point
 * per full-to-full fill-up interval, with last-five and all-time averages,
 * in the asset's (else the household's) units.
 */
export function FuelEconomyChart({ asset, logs }: { asset: Asset; logs: FuelLog[] }) {
  const [period, setPeriod] = useState<PeriodKey>("6M");
  const { data: household } = useQuery({ queryKey: ["household"], queryFn: getCurrentHousehold });
  const units = effectiveUnitSystem(asset.vehicle_details?.unit_system_override, household?.settings?.unit_system);
  const unit = economyUnitLabel(units);

  const months = PERIODS.find((p) => p.key === period)!.months;
  const all = mpgSeries(logs);
  const points = months == null ? all : all.filter((p) => p.performedAt.slice(0, 10) >= cutoff(months));
  const show = (mpg: number | null) => (mpg == null ? "—" : economyForDisplay(mpg, units).toFixed(1));

  return (
    <section className="fuel-economy" aria-labelledby="fuel-economy-heading">
      <h2 id="fuel-economy-heading">Fuel Economy</h2>
      <PeriodPicker value={period} onChange={setPeriod} label="Fuel economy time range" />
      {points.length < 2 ? (
        <div className="chart-empty">
          <strong>Not Enough Data Yet</strong>
          <p>Log at least two full fill-ups to see your fuel economy trend.</p>
        </div>
      ) : (
        <>
          <div className="stat-row">
            <div className="stat-tile">
              <span className="stat-label">Last 5 Avg</span>
              <span className="stat-value" data-testid="economy-last5">
                {show(trailingAverage(points))} <small>{unit}</small>
              </span>
            </div>
            <div className="stat-tile">
              <span className="stat-label">All-Time Avg</span>
              <span className="stat-value" data-testid="economy-all-time">
                {show(allTimeAverage(points))} <small>{unit}</small>
              </span>
            </div>
          </div>
          <EconomyLine values={points.map((p) => ({ date: p.performedAt, value: economyForDisplay(p.mpg, units) }))} unit={unit} />
        </>
      )}
    </section>
  );
}

function EconomyLine({ values, unit }: { values: { date: string; value: number }[]; unit: string }) {
  const W = 640;
  const H = 200;
  const pad = { top: 12, bottom: 24, left: 40, right: 12 };
  const lo = Math.min(...values.map((v) => v.value));
  const hi = Math.max(...values.map((v) => v.value));
  // Some headroom, and a visible band even when every point is the same.
  const span = Math.max(hi - lo, Math.max(hi * 0.05, 1));
  const min = lo - span * 0.15;
  const max = hi + span * 0.15;
  const x = (i: number) => pad.left + (values.length === 1 ? 0 : (i / (values.length - 1)) * (W - pad.left - pad.right));
  const y = (v: number) => pad.top + (1 - (v - min) / (max - min)) * (H - pad.top - pad.bottom);
  const path = values.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v.value).toFixed(1)}`).join(" ");
  const last = values.length - 1;

  return (
    <svg
      className="economy-chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`Fuel economy, ${values.length} fill-up intervals, from ${values[0].value.toFixed(1)} to ${values[last].value.toFixed(1)} ${unit}`}
      data-testid="fuel-economy-chart"
    >
      <line x1={pad.left} x2={W - pad.right} y1={H - pad.bottom} y2={H - pad.bottom} className="chart-axis" />
      <text x={pad.left - 6} y={y(hi) + 4} className="chart-tick" textAnchor="end">
        {hi.toFixed(0)}
      </text>
      <text x={pad.left - 6} y={y(lo) + 4} className="chart-tick" textAnchor="end">
        {lo.toFixed(0)}
      </text>
      <path d={path} className="economy-line" fill="none" />
      {values.map((v, i) => (
        <circle key={i} cx={x(i)} cy={y(v.value)} r={4} className="economy-point">
          <title>{`${formatDate(v.date)}: ${v.value.toFixed(1)} ${unit}`}</title>
        </circle>
      ))}
      <text x={x(0)} y={H - 6} className="chart-tick" textAnchor="start">
        {formatDate(values[0].date)}
      </text>
      {last > 0 && (
        <text x={x(last)} y={H - 6} className="chart-tick" textAnchor="end">
          {formatDate(values[last].date)}
        </text>
      )}
    </svg>
  );
}
