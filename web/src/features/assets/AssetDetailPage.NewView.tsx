import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { deleteAsset, getAsset, updateAsset } from "../../api/assets";
import type { AssetCreateInput, AssetStatus } from "../../api/types";
import { MaintenanceRecordsSection } from "../maintenance/MaintenanceRecordsSection";
import { SchedulesSection } from "../schedules/SchedulesSection";
import { ASSET_TYPES } from "./assetTypes";

function assetTypeBg(type: string): string {
  const colors: Record<string, string> = {
    vehicle: "#e8f0fe",
    equipment: "#fef3e2",
    property: "#e6f4ea",
    home_system: "#f3e8fd",
  };
  return colors[type] ?? "var(--bg-alt)";
}

function assetTypeAccent(type: string): string {
  const colors: Record<string, string> = {
    vehicle: "#1a73e8",
    equipment: "#e37400",
    property: "#0d804f",
    home_system: "#7b2cbf",
  };
  return colors[type] ?? "var(--accent)";
}

function GridField({
  label,
  value,
  type = "text",
  min,
  max,
  step,
  placeholder,
  readOnly,
  onChange,
}: {
  label: string;
  value: string | number | undefined;
  type?: string;
  min?: number | string;
  max?: number | string;
  step?: number | string;
  placeholder?: string;
  readOnly?: boolean;
  onChange?: (v: string) => void;
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
        readOnly={readOnly}
        value={value ?? ""}
        onChange={(e) => onChange?.(e.target.value)}
      />
    </div>
  );
}

export function AssetDetailPageNewView() {
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
        status: asset.status,
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

  const deleteMutation = useMutation({
    mutationFn: () => deleteAsset(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      navigate("/assets");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    saveMutation.mutate();
  }

  if (isLoading || !asset) return <p>Loading...</p>;

  const assetTypeLabel = ASSET_TYPES.find((t) => t.value === asset.asset_type)?.label ?? asset.asset_type;
  return (
    <div className="asset-detail-page">
      <header className="asset-header">
        <div className="asset-header-left">
          <div className="header-top-row">
            <span
              className="asset-type-badge"
              style={{ background: assetTypeBg(asset.asset_type), color: assetTypeAccent(asset.asset_type) }}
            >
              {assetTypeLabel}
            </span>
            <h1>{asset.name}</h1>
            <span className={`status-pill status-${asset.status}`}>{asset.status}</span>
          </div>
        </div>
        <div className="asset-header-right">
          <button type="button" className="secondary" onClick={() => { const next: AssetStatus = asset.status === "active" ? "archived" : "active"; setForm({ ...form, status: next }); }} disabled={saveMutation.isPending || deleteMutation.isPending}>
            {asset.status === "active" ? "Archive" : "Activate"}
          </button>
          <button type="button" className="danger" onClick={() => deleteMutation.mutate()} disabled={saveMutation.isPending}>
            Delete
          </button>
        </div>
      </header>

      <form className="asset-body" onSubmit={handleSubmit}>
        <section className="asset-info-panel">
          <h2>Information</h2>
          <div className="field-grid">
            <GridField label="Name" value={form.name ?? ""} onChange={(v) => setForm({ ...form, name: v })} />
            <GridField label="Status" value={form.status ?? "active"} readOnly />
            <div className="field-full">
              <label>Notes</label>
              <textarea
                rows={4}
                value={form.notes ?? ""}
                placeholder="Add notes about this asset..."
                onChange={(e) => setForm({ ...form, notes: e.target.value || undefined })}
              />
            </div>
          </div>

          <h2 style={{ marginTop: 24 }}>Purchase</h2>
          <div className="field-grid">
            <GridField label="Purchase Date" type="date" value={form.purchase_date ?? ""} onChange={(v) => setForm({ ...form, purchase_date: v })} />
            <GridField label="Purchase Cost" type="number" step="0.01" min="0" value={form.purchase_cost ?? ""} placeholder="0.00" onChange={(v) => setForm({ ...form, purchase_cost: v ? Number(v) : null })} />
          </div>
        </section>

        <aside className="asset-sidebar">
          {asset.asset_type === "vehicle" && form.vehicle_details && (
            <section className="detail-group">
              <h2>Vehicle Details</h2>
              <div className="field-grid field-compact">
                <GridField label="Make" value={form.vehicle_details.make ?? ""} onChange={(v) => setForm({ ...form, vehicle_details: { ...form.vehicle_details!, make: v } })} />
                <GridField label="Model" value={form.vehicle_details.model ?? ""} onChange={(v) => setForm({ ...form, vehicle_details: { ...form.vehicle_details!, model: v } })} />
                <GridField label="Year" type="number" value={form.vehicle_details.year ?? ""} placeholder="YYYY" onChange={(v) => setForm({ ...form, vehicle_details: { ...form.vehicle_details!, year: v ? Number(v) : null } })} />
                <GridField label="VIN" value={form.vehicle_details.vin ?? ""} onChange={(v) => setForm({ ...form, vehicle_details: { ...form.vehicle_details!, vin: v } })} />
                <GridField label="License Plate" value={form.vehicle_details.license_plate ?? ""} onChange={(v) => setForm({ ...form, vehicle_details: { ...form.vehicle_details!, license_plate: v } })} />
                <GridField label="Current Mileage" type="number" min="0" value={form.vehicle_details.current_mileage ?? ""} placeholder="0" onChange={(v) => setForm({ ...form, vehicle_details: { ...form.vehicle_details!, current_mileage: v ? Number(v) : null } })} />
                <GridField label="Mileage Unit" value={form.vehicle_details.mileage_unit ?? "mi"} onChange={(v) => setForm({ ...form, vehicle_details: { ...form.vehicle_details!, mileage_unit: v } })} />
                <GridField label="Fuel Type" value={form.vehicle_details.fuel_type ?? ""} placeholder="e.g. Gasoline" onChange={(v) => setForm({ ...form, vehicle_details: { ...form.vehicle_details!, fuel_type: v || null } })} />
              </div>
            </section>
          )}

          {asset.asset_type === "equipment" && form.equipment_details && (
            <section className="detail-group">
              <h2>Equipment Details</h2>
              <div className="field-grid field-compact">
                <GridField label="Manufacturer" value={form.equipment_details.manufacturer ?? ""} onChange={(v) => setForm({ ...form, equipment_details: { ...form.equipment_details!, manufacturer: v } })} />
                <GridField label="Model Number" value={form.equipment_details.model_number ?? ""} onChange={(v) => setForm({ ...form, equipment_details: { ...form.equipment_details!, model_number: v } })} />
                <GridField label="Serial Number" value={form.equipment_details.serial_number ?? ""} onChange={(v) => setForm({ ...form, equipment_details: { ...form.equipment_details!, serial_number: v } })} />
                <GridField label="Warranty Expiration" type="date" value={form.equipment_details.warranty_expiration ?? ""} onChange={(v) => setForm({ ...form, equipment_details: { ...form.equipment_details!, warranty_expiration: v } })} />
              </div>
            </section>
          )}

          {(asset.asset_type === "property" || asset.asset_type === "home_system") && form.property_details && (
            <section className="detail-group">
              <h2>Property Details</h2>
              <div className="field-grid field-compact">
                <GridField label="Address" value={form.property_details.address ?? ""} onChange={(v) => setForm({ ...form, property_details: { ...form.property_details!, address: v } })} />
                <GridField label="Install Date" type="date" value={form.property_details.install_date ?? ""} onChange={(v) => setForm({ ...form, property_details: { ...form.property_details!, install_date: v } })} />
              </div>
            </section>
          )}

          <section className="meta-panel">
            <h2>Metadata</h2>
            <dl className="meta-list">
              <dt>Created</dt>
              <dd>{new Date(asset.created_at).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}</dd>
              <dt>Last updated</dt>
              <dd>{new Date(asset.updated_at).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}</dd>
              <dt>Sync version</dt>
              <dd>v{asset.version}</dd>
              {asset.purchase_cost && <dt>Purchase cost</dt>}
              {asset.purchase_cost && (<dd>${(asset.purchase_cost as number).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</dd>)}
              {asset.vehicle_details?.current_mileage != null && (
                <>
                  <dt>Mileage</dt>
                  <dd>{(asset.vehicle_details.current_mileage as number).toLocaleString()} {asset.vehicle_details.mileage_unit}</dd>
                </>
              )}
            </dl>
          </section>
        </aside>
      </form>

      <div className="asset-bottom">
        <section className="asset-detail-panel">
          <h2>Maintenance Records</h2>
          <MaintenanceRecordsSection assetId={asset.id!} />
        </section>
        <section className="asset-detail-panel">
          <h2>Schedules</h2>
          <SchedulesSection assetId={asset.id!} />
        </section>
      </div>

      <button type="submit" style={{ display: "none" }} />
    </div>
  );
}

export default AssetDetailPageNewView;