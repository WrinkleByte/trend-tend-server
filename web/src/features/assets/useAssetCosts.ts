// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useQuery } from "@tanstack/react-query";
import { listFuelLogs } from "../../api/fuelLogs";
import { listMaintenanceRecords } from "../../api/maintenanceRecords";
import type { Asset } from "../../api/types";
import { costOfOwnership, todayIso } from "../../lib/costs";

/** The range picker shared by Cost Trends and Fuel Economy, as on mobile. */
export const PERIODS = [
  { key: "6M", label: "6M", months: 6 },
  { key: "1Y", label: "1Y", months: 12 },
  { key: "3Y", label: "3Y", months: 36 },
  { key: "ALL", label: "All", months: null },
] as const;
export type PeriodKey = (typeof PERIODS)[number]["key"];

/** Same queries (and keys) as the Overview, Service and Fuel tabs, so nothing is fetched twice. */
export function useAssetCosts(asset: Asset) {
  const tracksFuel = asset.asset_type === "vehicle";
  const records = useQuery({
    queryKey: ["maintenance-records", asset.id],
    queryFn: () => listMaintenanceRecords(asset.id),
  });
  const fuelLogs = useQuery({
    queryKey: ["fuel-logs", asset.id],
    queryFn: () => listFuelLogs(asset.id),
    enabled: tracksFuel,
  });
  const maintenance = (records.data ?? []).reduce((sum, r) => sum + (Number(r.cost) || 0), 0);
  const fuel = tracksFuel ? (fuelLogs.data ?? []).reduce((sum, f) => sum + (Number(f.total_cost) || 0), 0) : 0;
  const ownership = costOfOwnership({
    purchaseCost: asset.purchase_cost,
    purchaseDate: asset.purchase_date,
    maintenance,
    fuel,
    status: asset.status,
    salePrice: asset.sale_price,
    saleDate: asset.sale_date,
    today: todayIso(),
  });
  return {
    tracksFuel,
    records: records.data ?? [],
    fuelLogs: tracksFuel ? (fuelLogs.data ?? []) : [],
    loading: records.isLoading || (tracksFuel && fuelLogs.isLoading),
    ownership,
  };
}

