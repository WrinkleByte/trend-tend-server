import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { deleteAsset, getAsset, updateAsset } from "../../api/assets";
import type { AssetCreateInput, AssetStatus } from "../../api/types";
import { MaintenanceRecordsSection } from "../maintenance/MaintenanceRecordsSection";
import { SchedulesSection } from "../schedules/SchedulesSection";
import { FuelLogsSection } from "../trips/FuelLogsSection";
import { TripLogsSection } from "../trips/TripLogsSection";
import { AssetProfilePhoto } from "./AssetProfilePhoto";
import { ASSET_TYPES } from "./assetTypes";

function GridField({
  label,
  value,
  type = "text",
  min,
  max,
  step,
  placeholder,
  onChange,
}: {
  label: string;
  value: string | number | undefined;
  type?: string;
  min?: number | string;
  max?: number | string;
  step?: number | string;
  placeholder?: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="form-field">
      <label>{label}</label>
      <input
        type={type}
        min={min}
        max={max}
        step={step}
        placeholder={placeholder}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

export function AssetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: asset, isLoading } = useQuery({
    queryKey: ["assets", id],
    queryFn: () => getAsset(id!),
    enabled: !!id,
  });

  const [form, setForm] = useState<Partial<AssetCreateInput>>({});
  useEffect(() => {
    if (asset) {
      setForm({
        name: asset.name,
        notes: asset.notes ?? undefined,
        purchase_date: asset.purchase_date ?? undefined,
        purchase_cost: asset.purchase_cost ?? undefined,
        vehicle_details: asset.vehicle_details ? { ...asset.vehicle_details } : undefined,
        equipment_details: asset.equipment_details ? { ...asset.equipment_details } : undefined,
        property_details: asset.property_details ? { ...asset.property_details } : undefined,
      });
    }
  }, [asset]);

  const saveMutation = useMutation({
    mutationFn: () => updateAsset(id!, form),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets", id] }),
  });

  // Deliberately its own mutation, independent of the Save button below —
  // archiving is a one-click status flip, not something that should also
  // silently commit whatever unsaved edits happen to be sitting in the rest
  // of the form at the time.
  const statusMutation = useMutation({
    mutationFn: (status: AssetStatus) => updateAsset(id!, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets", id] }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteAsset(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      navigate("/");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    saveMutation.mutate();
  }

  if (isLoading || !asset) return <p>Loading…</p>;

  const assetTypeLabel = ASSET_TYPES.find((t) => t.value === asset.asset_type)?.label ?? asset.asset_type;

  return (
    <div className="asset-detail-page">
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
            className="secondary"
            disabled={statusMutation.isPending}
            onClick={() => statusMutation.mutate(asset.status === "active" ? "archived" : "active")}
          >
            {asset.status === "active" ? "Archive" : "Activate"}
          </button>
          <button
            type="button"
            className="danger"
            onClick={() => deleteMutation.mutate()}
            disabled={deleteMutation.isPending}
          >
            Delete
          </button>
        </div>
      </header>

      <form className="asset-body" onSubmit={handleSubmit}>
        <section className="asset-info-panel">
          <AssetProfilePhoto asset={asset} />

          <h2>Information</h2>
          <div className="field-grid">
            <GridField label="Name" value={form.name ?? ""} onChange={(v) => setForm({ ...form, name: v })} />
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
                  type="number"
                  min="0"
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
              <dd>{new Date(asset.updated_at).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}</dd>
              <dt>Sync version</dt>
              <dd>v{asset.version}</dd>
              {asset.purchase_cost != null && (
                <>
                  <dt>Purchase cost</dt>
                  <dd>
                    ${asset.purchase_cost.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
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
        <section className="asset-detail-panel">
          <MaintenanceRecordsSection assetId={asset.id} />
        </section>
        <section className="asset-detail-panel">
          <SchedulesSection assetId={asset.id} />
        </section>
        {asset.asset_type === "vehicle" && (
          <>
            <section className="asset-detail-panel">
              <TripLogsSection assetId={asset.id} />
            </section>
            <section className="asset-detail-panel">
              <FuelLogsSection assetId={asset.id} />
            </section>
          </>
        )}
      </div>
    </div>
  );
}
