// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { deleteAsset, getAsset, listAssets, updateAsset } from "../../api/assets";
import { useHouseholdMembers } from "../household/useHouseholdMembers";
import type { AssetCreateInput } from "../../api/types";
import { GridField } from "../../components/GridField";
import { MaintenanceRecordsSection } from "../maintenance/MaintenanceRecordsSection";
import { MaintenanceAlertsSection } from "../schedules/MaintenanceAlertsSection";
import { SchedulesSection } from "../schedules/SchedulesSection";
import { FuelLogsSection } from "../trips/FuelLogsSection";
import { TripLogsSection } from "../trips/TripLogsSection";
import { AttachmentsSection } from "../attachments/AttachmentsSection";
import { TabNav, type TabItem } from "../../components/ui/TabNav";
import { AssetOverview } from "./AssetOverview";
import { CostsSection } from "./CostsSection";
import { FuelEconomyPanel } from "../trips/FuelEconomyChart";
import { AssetProfilePhoto } from "./AssetProfilePhoto";
import { ASSET_TYPES } from "./assetTypes";
import { WHOLE_NUMBER_INPUT } from "../../components/wholeNumberInput";

export function AssetDetailPage() {
  const { id, tab } = useParams<{ id: string; tab?: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: asset, isLoading } = useQuery({
    queryKey: ["assets", id],
    queryFn: () => getAsset(id!),
    enabled: !!id,
  });

  // Only fetched for the "Located At" picker below -- a Valuable's optional
  // link to a property/home_system asset.
  const { data: allAssets } = useQuery({ queryKey: ["assets"], queryFn: () => listAssets() });
  const propertyAssets = (allAssets ?? []).filter(
    (a) => a.asset_type === "property" || a.asset_type === "home_system",
  );

  const { members, nameFor, pickerMembers, pickerLabel } = useHouseholdMembers();
  const [form, setForm] = useState<Partial<AssetCreateInput>>({});
  useEffect(() => {
    if (asset) {
      setForm({
        name: asset.name,
        notes: asset.notes ?? undefined,
        purchase_date: asset.purchase_date ?? undefined,
        purchase_cost: asset.purchase_cost ?? undefined,
        // Only sent (and only editable) once the asset is retired.
        ...(asset.status !== "active" ? { sale_price: asset.sale_price, sale_date: asset.sale_date } : {}),
        owner_user_id: asset.owner_user_id ?? undefined,
        vehicle_details: asset.vehicle_details ? { ...asset.vehicle_details } : undefined,
        equipment_details: asset.equipment_details ? { ...asset.equipment_details } : undefined,
        property_details: asset.property_details ? { ...asset.property_details } : undefined,
        valuable_details: asset.valuable_details ? { ...asset.valuable_details } : undefined,
      });
    }
  }, [asset]);

  const saveMutation = useMutation({
    mutationFn: () => updateAsset(id!, form),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets", id] }),
  });

  // Deliberately its own mutation, independent of the Save button below —
  // retiring is a one-click status flip, not something that should also
  // silently commit whatever unsaved edits happen to be sitting in the rest
  // of the form at the time. Calls the same PATCH /assets/{id} as Save, but
  // the backend only touches vehicle_details/equipment_details/property_details
  // when they're present in the request body (app/api/v1/assets.py's
  // `if payload.vehicle_details:` guards) -- sending status alone here never
  // risks wiping them, unlike the bug this mirrors on mobile (Vikunja #106,
  // fixed there with a dedicated writeDetails-free repository method; the
  // backend never had that bug since it does a real partial update).
  const statusMutation = useMutation({
    mutationFn: (change: Pick<AssetCreateInput, "status" | "sale_price" | "sale_date">) => updateAsset(id!, change),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets", id] }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteAsset(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      navigate("/inventory");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    saveMutation.mutate();
  }

  // A single click here used to delete the asset outright, no confirmation
  // at all -- lost a real vehicle's full history this way once (Vikunja
  // #34). Mirrors AdminHouseholdsSection.tsx's existing confirm() pattern.
  function handleDelete() {
    if (window.confirm(`Permanently delete "${asset?.name}" and all its maintenance, fuel, and trip history? This cannot be undone.`)) {
      deleteMutation.mutate();
    }
  }

  // "Retire"/"Restore" terminology and confirm() text mirror the mobile
  // apps' AssetFormView.swift/AssetFormScreen.kt exactly (Vikunja #106) --
  // this used to say "Archive"/"Activate" with no confirmation at all,
  // diverging from mobile on both wording and safety for what's the same
  // underlying status flip.
  function handleToggleStatus() {
    if (!asset) return;
    if (asset.status === "active") {
      if (
        window.confirm(
          `Retire "${asset.name}"? This will move it to the retired section. You can still view its history, but it won't appear in active lists.`,
        )
      ) {
        // Optional, like the mobile apps' retire dialog: blank means it
        // wasn't sold (scrapped, given away). Dated today; the Sale section
        // of the form can change it afterwards.
        const answer = window.prompt("What did it sell for? Leave blank if it wasn't sold.", "");
        if (answer === null) return;
        const cleaned = answer.trim().replace(/^\$/, "").replace(/,/g, "");
        const price = cleaned === "" ? null : Number(cleaned);
        if (price !== null && (!Number.isFinite(price) || price < 0)) {
          window.alert("Enter the sale price as a number, like 8500.");
          return;
        }
        statusMutation.mutate({
          status: "archived",
          sale_price: price,
          sale_date: price === null ? null : new Date().toLocaleDateString("en-CA"),
        });
      }
    } else if (
      window.confirm(
        `Restore "${asset.name}" to active? This will move it back to your active list.` +
          (asset.sale_price != null ? " The recorded sale price will be cleared." : ""),
      )
    ) {
      // Same as mobile: restoring means it wasn't sold after all.
      statusMutation.mutate({ status: "active", sale_price: null, sale_date: null });
    }
  }

  if (isLoading || !asset) return <p>Loading…</p>;

  const assetTypeLabel = ASSET_TYPES.find((t) => t.value === asset.asset_type)?.label ?? asset.asset_type;

  // One tab per kind of record, each a real address (/assets/<id>/<tab>).
  // The page used to stack all of these in a single scroll several screens
  // long. The edit form's state lives in this component, which stays
  // mounted across tab changes, so unsaved edits survive a look at another
  // tab.
  const base = `/assets/${asset.id}`;
  const isVehicle = asset.asset_type === "vehicle";
  const tabs: (TabItem & { key: string })[] = [
    { key: "overview", to: base, label: "Overview", end: true },
    { key: "service", to: `${base}/service`, label: "Service" },
    ...(isVehicle
      ? [
          { key: "fuel", to: `${base}/fuel`, label: "Fuel" },
          { key: "trips", to: `${base}/trips`, label: "Trips" },
        ]
      : []),
    { key: "costs", to: `${base}/costs`, label: "Costs" },
    { key: "reminders", to: `${base}/reminders`, label: "Reminders" },
    ...(asset.asset_type === "valuable" ? [{ key: "documents", to: `${base}/documents`, label: "Documents" }] : []),
    { key: "details", to: `${base}/details`, label: "Details" },
  ];
  const activeTab = tab ?? "overview";
  if (!tabs.some((t) => t.key === activeTab)) return <Navigate to={base} replace />;

  return (
    <div className="asset-detail-page">
      <nav className="page-trail" aria-label="Breadcrumb">
        <Link to="/inventory">Assets</Link>
        <span aria-hidden="true">/</span>
      </nav>
      <header className="asset-header">
        <div className="asset-header-left">
          <div className="header-top-row">
            <span className="asset-type-badge">{assetTypeLabel}</span>
            <h1>{asset.name}</h1>
            <span className={`status-pill status-${asset.status}`}>{asset.status}</span>
          </div>
        </div>
        <div className="asset-header-right">
          <button
            type="button"
            className={asset.status === "active" ? "danger" : "secondary"}
            disabled={statusMutation.isPending}
            onClick={handleToggleStatus}
          >
            {asset.status === "active" ? "Retire" : "Restore to Active"}
          </button>
          <button type="button" className="danger" onClick={handleDelete} disabled={deleteMutation.isPending}>
            Delete
          </button>
        </div>
      </header>

      <TabNav label="Asset sections" items={tabs} />

      {activeTab === "overview" && (
        <div className="asset-bottom">
          <AssetOverview asset={asset} />
          <section className="asset-detail-panel">
            <MaintenanceAlertsSection
              assetId={asset.id}
              assetType={asset.asset_type}
              currentUsage={asset.vehicle_details?.current_mileage ?? null}
            />
          </section>
        </div>
      )}

      <form className="asset-body" onSubmit={handleSubmit} hidden={activeTab !== "details"}>
        <section className="asset-info-panel">
          <AssetProfilePhoto asset={asset} />

          <h2>Information</h2>
          <div className="field-grid">
            <GridField label="Name" value={form.name ?? ""} onChange={(v) => setForm({ ...form, name: v })} />
            {(members?.length ?? 0) > 1 && (
              <div>
                <label htmlFor="asset-owner">Owner</label>
                <select
                  id="asset-owner"
                  value={form.owner_user_id ?? ""}
                  onChange={(e) => setForm({ ...form, owner_user_id: e.target.value || undefined })}
                >
                  <option value="">Unassigned</option>
                  {pickerMembers.map((m) => (
                    <option key={m.user_id} value={m.user_id}>
                      {pickerLabel(m)}
                    </option>
                  ))}
                </select>
                <span className="field-hint">
                  Only affects who sees this under &ldquo;Only show my stuff&rdquo;. Everyone in the
                  household can still view and edit it.
                </span>
              </div>
            )}
            <div className="field-full">
              <label>Notes</label>
              <textarea
                rows={4}
                value={form.notes ?? ""}
                placeholder="Add notes about this asset…"
                onChange={(e) => setForm({ ...form, notes: e.target.value || undefined })}
              />
            </div>
          </div>

          <h2 style={{ marginTop: 24 }}>Purchase</h2>
          <div className="field-grid">
            <GridField
              label="Purchase date"
              type="date"
              value={form.purchase_date ?? ""}
              onChange={(v) => setForm({ ...form, purchase_date: v || undefined })}
            />
            <GridField
              label="Purchase cost"
              type="number"
              step="0.01"
              min="0"
              value={form.purchase_cost ?? ""}
              placeholder="0.00"
              onChange={(v) => setForm({ ...form, purchase_cost: v ? Number(v) : undefined })}
            />
          </div>

          {asset.status !== "active" && (
            <>
              <h2 style={{ marginTop: 24 }}>Sale</h2>
              <div className="field-grid">
                <GridField
                  label="Sale date"
                  type="date"
                  value={form.sale_date ?? ""}
                  onChange={(v) => setForm({ ...form, sale_date: v || null })}
                />
                <GridField
                  label="Sale price"
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.sale_price ?? ""}
                  placeholder="Not sold"
                  onChange={(v) => setForm({ ...form, sale_price: v ? Number(v) : null })}
                />
              </div>
            </>
          )}

          {asset.asset_type === "vehicle" && (
            <>
              <h2 style={{ marginTop: 24 }}>Vehicle details</h2>
              <div className="field-grid field-compact">
                <GridField
                  label="Make"
                  value={form.vehicle_details?.make ?? ""}
                  onChange={(v) => setForm({ ...form, vehicle_details: { ...form.vehicle_details, make: v } })}
                />
                <GridField
                  label="Model"
                  value={form.vehicle_details?.model ?? ""}
                  onChange={(v) => setForm({ ...form, vehicle_details: { ...form.vehicle_details, model: v } })}
                />
                <GridField
                  label="Year"
                  type="number"
                  value={form.vehicle_details?.year ?? ""}
                  placeholder="YYYY"
                  onChange={(v) =>
                    setForm({
                      ...form,
                      vehicle_details: { ...form.vehicle_details, year: v ? Number(v) : null },
                    })
                  }
                />
                <GridField
                  label="License plate"
                  value={form.vehicle_details?.license_plate ?? ""}
                  onChange={(v) =>
                    setForm({ ...form, vehicle_details: { ...form.vehicle_details, license_plate: v } })
                  }
                />
                <GridField
                  label="Current mileage"
                  {...WHOLE_NUMBER_INPUT}
                  value={form.vehicle_details?.current_mileage ?? ""}
                  placeholder="0"
                  onChange={(v) =>
                    setForm({
                      ...form,
                      vehicle_details: { ...form.vehicle_details, current_mileage: v ? Number(v) : null },
                    })
                  }
                />
                <GridField
                  label="Mileage unit"
                  value={form.vehicle_details?.mileage_unit ?? "mi"}
                  onChange={(v) =>
                    setForm({ ...form, vehicle_details: { ...form.vehicle_details, mileage_unit: v } })
                  }
                />
                <GridField
                  label="Fuel type"
                  value={form.vehicle_details?.fuel_type ?? ""}
                  placeholder="e.g. Gasoline"
                  onChange={(v) =>
                    setForm({ ...form, vehicle_details: { ...form.vehicle_details, fuel_type: v || null } })
                  }
                />
              </div>
            </>
          )}

          {asset.asset_type === "equipment" && (
            <>
              <h2 style={{ marginTop: 24 }}>Equipment details</h2>
              <div className="field-grid field-compact">
                <GridField
                  label="Manufacturer"
                  value={form.equipment_details?.manufacturer ?? ""}
                  onChange={(v) =>
                    setForm({ ...form, equipment_details: { ...form.equipment_details, manufacturer: v } })
                  }
                />
                <GridField
                  label="Model number"
                  value={form.equipment_details?.model_number ?? ""}
                  onChange={(v) =>
                    setForm({ ...form, equipment_details: { ...form.equipment_details, model_number: v } })
                  }
                />
                <GridField
                  label="Serial number"
                  value={form.equipment_details?.serial_number ?? ""}
                  onChange={(v) =>
                    setForm({ ...form, equipment_details: { ...form.equipment_details, serial_number: v } })
                  }
                />
                <GridField
                  label="Warranty expiration"
                  type="date"
                  value={form.equipment_details?.warranty_expiration ?? ""}
                  onChange={(v) =>
                    setForm({
                      ...form,
                      equipment_details: { ...form.equipment_details, warranty_expiration: v || null },
                    })
                  }
                />
              </div>
            </>
          )}

          {asset.asset_type === "valuable" && (
            <>
              <h2 style={{ marginTop: 24 }}>Valuable details</h2>
              <div className="field-grid field-compact">
                <GridField
                  label="Manufacturer"
                  value={form.valuable_details?.manufacturer ?? ""}
                  onChange={(v) =>
                    setForm({ ...form, valuable_details: { ...form.valuable_details, manufacturer: v } })
                  }
                />
                <GridField
                  label="Model number"
                  value={form.valuable_details?.model_number ?? ""}
                  onChange={(v) =>
                    setForm({ ...form, valuable_details: { ...form.valuable_details, model_number: v } })
                  }
                />
                <GridField
                  label="Serial number"
                  value={form.valuable_details?.serial_number ?? ""}
                  onChange={(v) =>
                    setForm({ ...form, valuable_details: { ...form.valuable_details, serial_number: v } })
                  }
                />
                <GridField
                  label="Warranty expiration"
                  type="date"
                  value={form.valuable_details?.warranty_expiration ?? ""}
                  onChange={(v) =>
                    setForm({
                      ...form,
                      valuable_details: { ...form.valuable_details, warranty_expiration: v || null },
                    })
                  }
                />
                <GridField
                  label="Store / purchased at"
                  value={form.valuable_details?.purchase_location ?? ""}
                  onChange={(v) =>
                    setForm({ ...form, valuable_details: { ...form.valuable_details, purchase_location: v || null } })
                  }
                />
                <div className="field-full">
                  <label>Located at</label>
                  <select
                    value={form.valuable_details?.linked_property_asset_id ?? ""}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        valuable_details: {
                          ...form.valuable_details,
                          linked_property_asset_id: e.target.value || null,
                        },
                      })
                    }
                  >
                    <option value="">None</option>
                    {propertyAssets.map((property) => (
                      <option key={property.id} value={property.id}>
                        {property.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </>
          )}

          {(asset.asset_type === "property" || asset.asset_type === "home_system") && (
            <>
              <h2 style={{ marginTop: 24 }}>Property details</h2>
              <div className="field-grid field-compact">
                <GridField
                  label="Address"
                  value={form.property_details?.address ?? ""}
                  onChange={(v) => setForm({ ...form, property_details: { ...form.property_details, address: v } })}
                />
                <GridField
                  label="Install date"
                  type="date"
                  value={form.property_details?.install_date ?? ""}
                  onChange={(v) =>
                    setForm({ ...form, property_details: { ...form.property_details, install_date: v || null } })
                  }
                />
              </div>
            </>
          )}

          <div className="form-actions" style={{ marginTop: 24 }}>
            <button type="submit" disabled={saveMutation.isPending}>
              {saveMutation.isPending ? "Saving…" : "Save"}
            </button>
            {saveMutation.isSuccess && <span>Saved.</span>}
          </div>
        </section>

        <aside className="asset-sidebar">
          <section className="meta-panel">
            <h2>Metadata</h2>
            <dl className="meta-list">
              <dt>Created</dt>
              <dd>{new Date(asset.created_at).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}</dd>
              <dt>Last updated</dt>
              <dd>
                {new Date(asset.updated_at).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}
                {/* Null for rows that predate the attribution column and for
                    imported rows — omit the clause entirely rather than
                    printing "by unknown". */}
                {asset.updated_by_user_id && <> by {nameFor(asset.updated_by_user_id)}</>}
              </dd>
              {(members?.length ?? 0) > 1 && (
                <>
                  <dt>Owner</dt>
                  <dd>{nameFor(asset.owner_user_id) ?? "Unassigned"}</dd>
                </>
              )}
              {asset.purchase_cost != null && (
                <>
                  <dt>Purchase cost</dt>
                  <dd>
                    ${Number(asset.purchase_cost).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </dd>
                </>
              )}
              {asset.sale_price != null && (
                <>
                  <dt>Sold for</dt>
                  <dd>
                    ${Number(asset.sale_price).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                    {asset.sale_date ? ` on ${asset.sale_date}` : ""}
                  </dd>
                </>
              )}
              {asset.vehicle_details?.current_mileage != null && (
                <>
                  <dt>Mileage</dt>
                  <dd>
                    {asset.vehicle_details.current_mileage.toLocaleString()} {asset.vehicle_details.mileage_unit}
                  </dd>
                </>
              )}
            </dl>
          </section>
        </aside>
      </form>

      <div className="asset-bottom">
        {activeTab === "service" && (
          <section className="asset-detail-panel">
            <MaintenanceRecordsSection assetId={asset.id} assetType={asset.asset_type} />
          </section>
        )}
        {activeTab === "reminders" && (
          <section className="asset-detail-panel">
            <SchedulesSection assetId={asset.id} assetType={asset.asset_type} />
          </section>
        )}
        {activeTab === "documents" && (
          <section className="asset-detail-panel">
            <h2>Documents &amp; Receipts</h2>
            <AttachmentsSection
              entityType="asset"
              entityId={asset.id}
              addButtonLabel="Add Document or Photo"
              emptyLabel="No documents or receipts attached."
            />
          </section>
        )}
        {activeTab === "trips" && (
          <section className="asset-detail-panel">
            <TripLogsSection assetId={asset.id} />
          </section>
        )}
        {activeTab === "fuel" && (
          <>
            <section className="asset-detail-panel">
              <FuelEconomyPanel asset={asset} />
            </section>
            <section className="asset-detail-panel">
              <FuelLogsSection assetId={asset.id} />
            </section>
          </>
        )}
        {activeTab === "costs" && (
          <section className="asset-detail-panel">
            <CostsSection asset={asset} />
          </section>
        )}
      </div>
    </div>
  );
}
