// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { listAssets } from "../../api/assets";
import { listFuelLogs } from "../../api/fuelLogs";
import { getCurrentHousehold } from "../../api/households";
import { listMaintenanceRecords } from "../../api/maintenanceRecords";
import { listMaintenanceSchedules } from "../../api/maintenanceSchedules";
import type { Asset } from "../../api/types";
import { EmptyState } from "../../components/ui/EmptyState";
import { Icon } from "../../components/ui/Icon";
import { PageHeader } from "../../components/ui/PageHeader";
import { formatDate, formatMoney } from "../../lib/format";
import { computeAlerts, displayCategory, type ScheduleAlert } from "../schedules/maintenanceAlerts";

function dueText(alert: ScheduleAlert): string {
  const parts: string[] = [];
  if (alert.daysUntilDue != null) {
    const d = alert.daysUntilDue;
    parts.push(d < 0 ? `${-d} day${-d === 1 ? "" : "s"} overdue` : d === 0 ? "Due today" : `Due in ${d} day${d === 1 ? "" : "s"}`);
  }
  if (alert.usageUntilDue != null) {
    const u = alert.usageUntilDue;
    parts.push(u < 0 ? `${(-u).toLocaleString()} mi overdue` : `Due in ${u.toLocaleString()} mi`);
  }
  return parts.join(" · ");
}

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toLocaleDateString("en-CA");
}

/** The landing page: what needs attention across the whole household, so
 * nobody has to open each asset in turn to find out. Read-only; every row
 * links to the place where the work is done. */
export function HomePage() {
  const { data: household } = useQuery({ queryKey: ["household"], queryFn: getCurrentHousehold });
  const { data: assets } = useQuery({ queryKey: ["assets"], queryFn: () => listAssets() });
  const { data: schedules } = useQuery({ queryKey: ["maintenance-schedules"], queryFn: () => listMaintenanceSchedules() });
  const { data: records } = useQuery({ queryKey: ["maintenance-records"], queryFn: () => listMaintenanceRecords() });
  const { data: fuelLogs } = useQuery({ queryKey: ["fuel-logs"], queryFn: () => listFuelLogs() });

  if (!assets || !schedules || !records || !fuelLogs) return <p>Loading…</p>;

  const active = assets.filter((a) => a.status === "active");
  const byId = new Map<string, Asset>(assets.map((a) => [a.id, a]));

  const due = active
    .flatMap((asset) =>
      computeAlerts(
        schedules.filter((s) => s.asset_id === asset.id),
        asset.vehicle_details?.current_mileage ?? null,
      ).map((alert) => ({ asset, alert })),
    )
    .sort((a, b) => {
      if (a.alert.severity !== b.alert.severity) return a.alert.severity === "overdue" ? -1 : 1;
      return (a.alert.daysUntilDue ?? 9999) - (b.alert.daysUntilDue ?? 9999);
    });
  const dueIds = new Set(due.map((d) => d.alert.schedule.id));

  const comingUp = schedules
    .filter((s) => s.active && s.dismissed_at == null && s.next_due_date && !dueIds.has(s.id))
    .filter((s) => byId.get(s.asset_id)?.status === "active")
    .sort((a, b) => a.next_due_date!.localeCompare(b.next_due_date!))
    .slice(0, 5);

  const yearAgo = isoDaysAgo(365);
  const serviceSpend = records.filter((r) => r.performed_at >= yearAgo).reduce((sum, r) => sum + Number(r.cost ?? 0), 0);
  const fuelSpend = fuelLogs.filter((f) => f.performed_at >= yearAgo).reduce((sum, f) => sum + Number(f.total_cost ?? 0), 0);

  const recent = [
    ...records.map((r) => ({
      id: r.id,
      assetId: r.asset_id,
      date: r.performed_at,
      label: r.description || displayCategory(r.category, r.custom_category),
      cost: r.cost,
      tab: "service",
    })),
    ...fuelLogs.map((f) => ({
      id: f.id,
      assetId: f.asset_id,
      date: f.performed_at,
      label: "Fuel",
      cost: f.total_cost,
      tab: "fuel",
    })),
  ]
    .sort((a, b) => b.date.localeCompare(a.date))
    .slice(0, 6);

  const overdueCount = due.filter((d) => d.alert.severity === "overdue").length;

  if (assets.length === 0) {
    return (
      <div>
        <PageHeader title={household ? household.name : "Home"} />
        <EmptyState title="Nothing here yet">
          Add your first vehicle, piece of equipment or property on the <Link to="/inventory">Assets</Link> page, or bring
          records in from another app under <Link to="/data/import">Import &amp; export</Link>.
        </EmptyState>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title={household ? household.name : "Home"} subtitle="What needs attention across your household." />

      <div className="stat-row">
        <Link to="/inventory" className="stat-tile">
          <span className="stat-label">Active assets</span>
          <span className="stat-value">{active.length}</span>
        </Link>
        <div className={`stat-tile${overdueCount ? " stat-tile-alert" : ""}`}>
          <span className="stat-label">Due or overdue</span>
          <span className="stat-value">{due.length}</span>
        </div>
        <div className="stat-tile">
          <span className="stat-label">Service · 12 months</span>
          <span className="stat-value">{formatMoney(serviceSpend)}</span>
        </div>
        <div className="stat-tile">
          <span className="stat-label">Fuel · 12 months</span>
          <span className="stat-value">{formatMoney(fuelSpend)}</span>
        </div>
      </div>

      <div className="home-grid">
        <section className="panel">
          <h2>Needs attention</h2>
          {due.length === 0 ? (
            <p className="quiet-line">
              <Icon name="check" size={18} /> Nothing is due right now.
            </p>
          ) : (
            <ul className="row-list">
              {due.map(({ asset, alert }) => (
                <li key={alert.schedule.id}>
                  <Link to={`/assets/${asset.id}`} className="row-link">
                    <span className={`row-dot row-dot-${alert.severity}`} aria-hidden="true" />
                    <span className="row-main">
                      <strong>{alert.schedule.name}</strong>
                      <span>{asset.name}</span>
                    </span>
                    <span className={`row-meta row-meta-${alert.severity}`}>{dueText(alert)}</span>
                    <Icon name="chevron" size={16} />
                  </Link>
                </li>
              ))}
            </ul>
          )}

          {comingUp.length > 0 && (
            <>
              <h3 className="panel-subheading">Coming up</h3>
              <ul className="row-list">
                {comingUp.map((s) => (
                  <li key={s.id}>
                    <Link to={`/assets/${s.asset_id}/reminders`} className="row-link">
                      <span className="row-dot" aria-hidden="true" />
                      <span className="row-main">
                        <strong>{s.name}</strong>
                        <span>{byId.get(s.asset_id)?.name}</span>
                      </span>
                      <span className="row-meta">{formatDate(s.next_due_date)}</span>
                      <Icon name="chevron" size={16} />
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>

        <section className="panel">
          <h2>Recent activity</h2>
          {recent.length === 0 ? (
            <p className="quiet-line">No service or fuel has been logged yet.</p>
          ) : (
            <ul className="row-list">
              {recent.map((item) => (
                <li key={item.id}>
                  <Link to={`/assets/${item.assetId}/${item.tab}`} className="row-link">
                    <span className="row-main">
                      <strong>{item.label}</strong>
                      <span>
                        {byId.get(item.assetId)?.name} · {formatDate(item.date)}
                      </span>
                    </span>
                    {item.cost != null && <span className="row-meta">{formatMoney(item.cost)}</span>}
                    <Icon name="chevron" size={16} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
