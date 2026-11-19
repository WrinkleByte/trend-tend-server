// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { listFuelLogs } from "../../api/fuelLogs";
import { listMaintenanceRecords } from "../../api/maintenanceRecords";
import type { Asset } from "../../api/types";
import { formatDate, formatMoney } from "../../lib/format";
import { useAssetCosts } from "./useAssetCosts";

/** The numbers at the top of an asset's Overview tab. Shares its queries
 * with the Service and Fuel tabs (same query keys), so switching tabs
 * doesn't refetch. */
export function AssetOverview({ asset }: { asset: Asset }) {
  const { data: records } = useQuery({
    queryKey: ["maintenance-records", asset.id],
    queryFn: () => listMaintenanceRecords(asset.id),
  });
  const isVehicle = asset.asset_type === "vehicle";
  const { data: fuelLogs } = useQuery({
    queryKey: ["fuel-logs", asset.id],
    queryFn: () => listFuelLogs(asset.id),
    enabled: isVehicle,
  });

  const serviceTotal = (records ?? []).reduce((sum, r) => sum + Number(r.cost ?? 0), 0);
  const fuelTotal = (fuelLogs ?? []).reduce((sum, f) => sum + Number(f.total_cost ?? 0), 0);
  const lastService = (records ?? []).map((r) => r.performed_at).sort().at(-1);
  const mileage = asset.vehicle_details?.current_mileage;
  const { ownership } = useAssetCosts(asset);

  return (
    <div className="stat-row">
      {isVehicle && mileage != null && (
        <div className="stat-tile">
          <span className="stat-label">Odometer</span>
          <span className="stat-value">
            {mileage.toLocaleString()} <small>{asset.vehicle_details?.mileage_unit}</small>
          </span>
        </div>
      )}
      <div className="stat-tile">
        <span className="stat-label">Service cost</span>
        <span className="stat-value">{formatMoney(serviceTotal)}</span>
        <span className="stat-note">
          {records?.length ?? 0} record{records?.length === 1 ? "" : "s"}
          {lastService ? ` · last ${formatDate(lastService)}` : ""}
        </span>
      </div>
      {isVehicle && (
        <div className="stat-tile">
          <span className="stat-label">Fuel cost</span>
          <span className="stat-value">{formatMoney(fuelTotal)}</span>
          <span className="stat-note">
            {fuelLogs?.length ?? 0} fill-up{fuelLogs?.length === 1 ? "" : "s"}
          </span>
        </div>
      )}
      {/* The bottom line, as on the apps' Cost Trends row; the breakdown is on the Costs tab. */}
      <Link className="stat-tile" to={`/assets/${asset.id}/costs`} data-testid="overview-cost-of-ownership">
        <span className="stat-label">{ownership.saleKnown ? "Net cost of ownership" : "Cost of ownership"}</span>
        <span className="stat-value">{formatMoney(ownership.netCost)}</span>
        <span className="stat-note">
          {ownership.perYear != null
            ? `${formatMoney(ownership.perYear)} per year owned`
            : ownership.purchaseKnown
              ? `Bought for ${formatMoney(ownership.purchase)}${asset.purchase_date ? ` · ${formatDate(asset.purchase_date)}` : ""}`
              : "No purchase price entered"}
        </span>
      </Link>
    </div>
  );
}
