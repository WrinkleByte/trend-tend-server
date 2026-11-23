// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useState } from "react";
import type { Asset } from "../../api/types";
import { useQuery } from "@tanstack/react-query";
import { getCurrentHousehold } from "../../api/households";
import { costTrend, effectiveUnitSystem, perKilometre, runningCost, todayIso, type CostTrend } from "../../lib/costs";
import { formatDate, formatMoney } from "../../lib/format";
import { PERIODS, useAssetCosts, type PeriodKey } from "./useAssetCosts";
import { fuelReadingCountsAsHours } from "../trips/fuelReading";

export function PeriodPicker({ value, onChange, label }: { value: PeriodKey; onChange: (k: PeriodKey) => void; label: string }) {
  return (
    <div className="period-picker" role="group" aria-label={label}>
      {PERIODS.map((p) => (
        <button
          key={p.key}
          type="button"
          className={p.key === value ? "active" : ""}
          aria-pressed={p.key === value}
          onClick={() => onChange(p.key)}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}

/**
 * The asset's Costs tab: the mobile apps' Cost Trends screen. Spending by
 * month (or year, for a long "All"), then the total cost of ownership.
 */
export function CostsSection({ asset }: { asset: Asset }) {
  const [period, setPeriod] = useState<PeriodKey>("1Y");
  const { tracksFuel, records, fuelLogs, loading, ownership } = useAssetCosts(asset);
  const { data: household } = useQuery({ queryKey: ["household"], queryFn: getCurrentHousehold });
  if (loading) return <p>Loading…</p>;

  // Vikunja #131: service + fuel per mile/km (vehicles) or per hour (equipment).
  const isEquipment = asset.asset_type === "equipment";
  const running =
    asset.asset_type === "vehicle" || isEquipment
      ? runningCost(
          records.map((r) => ({ performedAt: r.performed_at, amount: r.cost, reading: r.odometer_reading })),
          // Equipment set to record an odometer at fill-ups: its fuel still costs, but those
          // miles are not hours, so they don't stretch the per-hour figure.
          fuelLogs.map((f) => ({
            performedAt: f.performed_at,
            amount: f.total_cost,
            reading: fuelReadingCountsAsHours(asset) ? f.odometer_reading : null,
          })),
          // Equipment's current hours aren't in the web API; its service records' readings still count.
          isEquipment ? null : asset.vehicle_details?.current_mileage,
          isEquipment,
        )
      : null;
  const metric =
    !isEquipment &&
    effectiveUnitSystem(asset.vehicle_details?.unit_system_override, household?.settings?.unit_system) === "metric";

  const months = PERIODS.find((p) => p.key === period)!.months;
  const trend = costTrend(
    records.map((r) => ({ performedAt: r.performed_at, amount: r.cost })),
    fuelLogs.map((f) => ({ performedAt: f.performed_at, amount: f.total_cost })),
    months,
    todayIso(),
  );
  const spent = trend.serviceTotal + trend.fuelTotal;

  return (
    <div className="costs-section">
      <h2>Cost Trends</h2>
      <PeriodPicker value={period} onChange={setPeriod} label="Time range" />

      <h3>{trend.yearly ? "Spending by Year" : "Spending by Month"}</h3>
      {spent > 0 ? (
        <>
          <div className="chart-legend" aria-hidden="true">
            <span>
              <i className="swatch swatch-service" /> Service
            </span>
            {tracksFuel && (
              <span>
                <i className="swatch swatch-fuel" /> Fuel
              </span>
            )}
          </div>
          <CostBars trend={trend} />
        </>
      ) : (
        <div className="chart-empty">
          <strong>No Costs in This Period</strong>
          <p>
            {tracksFuel
              ? "Costs on service records and fuel logs show up here by month."
              : "Costs on service records show up here by month."}
          </p>
        </div>
      )}
      <dl className="cost-rows">
        <CostRow label="Service" value={formatMoney(trend.serviceTotal)} />
        {tracksFuel && <CostRow label="Fuel" value={formatMoney(trend.fuelTotal)} />}
        <CostRow label="Spent in Period" value={formatMoney(spent)} strong testId="cost-period-total" />
      </dl>

      <h2>Cost of Ownership</h2>
      <dl className="cost-rows">
        <CostRow
          label="Purchase Price"
          value={ownership.purchaseKnown ? formatMoney(ownership.purchase) : "Not entered"}
          note={ownership.purchaseKnown && asset.purchase_date ? formatDate(asset.purchase_date) : undefined}
        />
        <CostRow label="Total Maintenance Cost" value={formatMoney(ownership.maintenance)} />
        {tracksFuel && <CostRow label="Total Fuel Cost" value={formatMoney(ownership.fuel)} />}
        {ownership.saleKnown && (
          <CostRow
            label={`Sold For${asset.sale_date ? ` on ${formatDate(asset.sale_date)}` : ""}`}
            value={`−${formatMoney(ownership.sale)}`}
          />
        )}
        <CostRow
          label={ownership.saleKnown ? "Net Cost of Ownership" : "Total Cost of Ownership"}
          value={formatMoney(ownership.netCost)}
          strong
          testId="total-cost-of-ownership"
        />
        {ownership.perYear != null && <CostRow label="Per Year Owned" value={formatMoney(ownership.perYear)} />}
        {running && (
          <CostRow
            label={`Running Cost per ${isEquipment ? "Hour" : metric ? "Kilometre" : "Mile"}`}
            value={formatMoney(metric ? perKilometre(running.perUnit) : running.perUnit)}
            testId="running-cost"
          />
        )}
      </dl>
      {running && (
        <p className="field-hint">
          Running cost is service and fuel over the {isEquipment ? "hours" : "distance"} you&apos;ve logged; it leaves
          out the purchase price.
        </p>
      )}
      {!ownership.purchaseKnown && (
        <p className="field-hint">Add a purchase price (Details tab) to include what it cost to buy.</p>
      )}
    </div>
  );
}

function CostRow({
  label,
  value,
  note,
  strong,
  testId,
}: {
  label: string;
  value: string;
  note?: string;
  strong?: boolean;
  testId?: string;
}) {
  return (
    <div className={strong ? "cost-row cost-row-total" : "cost-row"} data-testid={testId}>
      <dt>
        {label}
        {note && <span className="cost-row-note"> · {note}</span>}
      </dt>
      <dd>{value}</dd>
    </div>
  );
}

/** Stacked bars, service under fuel, one per month (or year). SVG with no
 * chart library: two series and a handful of bars don't justify one. */
function CostBars({ trend }: { trend: CostTrend }) {
  const W = 640;
  const H = 200;
  const top = 8;
  const bottom = 24;
  const plotH = H - top - bottom;
  const n = trend.periods.length;
  const max = Math.max(...trend.periods.map((p) => p.service + p.fuel), 1);
  const slot = W / n;
  const barW = Math.max(2, Math.min(40, slot * 0.7));
  // Axis ticks: first, middle and last, as on mobile.
  const ticks = [...new Set([0, Math.floor((n - 1) / 2), n - 1])];
  const summary = trend.periods
    .filter((p) => p.service + p.fuel > 0)
    .map((p) => `${p.label}: ${formatMoney(p.service + p.fuel)}`)
    .join("; ");

  return (
    <svg
      className="cost-chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`Spending ${trend.yearly ? "by year" : "by month"}. ${summary}`}
      data-testid="cost-trend-chart"
    >
      <line x1={0} x2={W} y1={top + plotH} y2={top + plotH} className="chart-axis" />
      {trend.periods.map((p, i) => {
        const x = i * slot + (slot - barW) / 2;
        const sH = (p.service / max) * plotH;
        const fH = (p.fuel / max) * plotH;
        return (
          <g key={p.start}>
            <title>{`${p.label}: service ${formatMoney(p.service)}, fuel ${formatMoney(p.fuel)}`}</title>
            {p.service > 0 && <rect x={x} y={top + plotH - sH} width={barW} height={sH} className="bar-service" rx={2} />}
            {p.fuel > 0 && <rect x={x} y={top + plotH - sH - fH} width={barW} height={fH} className="bar-fuel" rx={2} />}
          </g>
        );
      })}
      {ticks.map((i) => (
        <text
          key={i}
          x={i * slot + slot / 2}
          y={H - 6}
          className="chart-tick"
          textAnchor={i === 0 && n > 1 ? "start" : i === n - 1 && n > 1 ? "end" : "middle"}
        >
          {trend.periods[i].label}
        </text>
      ))}
    </svg>
  );
}
