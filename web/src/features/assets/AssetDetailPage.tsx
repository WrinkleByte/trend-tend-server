import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { deleteAsset, getAsset, updateAsset } from "../../api/assets";
import type { AssetCreateInput } from "../../api/types";
import { MaintenanceRecordsSection } from "../maintenance/MaintenanceRecordsSection";
import { SchedulesSection } from "../schedules/SchedulesSection";
import { AssetProfilePhoto } from "./AssetProfilePhoto";

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
        notes: asset.notes,
        purchase_date: asset.purchase_date,
        purchase_cost: asset.purchase_cost,
        vehicle_details: asset.vehicle_details ?? undefined,
        equipment_details: asset.equipment_details ?? undefined,
        property_details: asset.property_details ?? undefined,
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
      navigate("/");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    saveMutation.mutate();
  }

  if (isLoading || !asset) return <p>Loading…</p>;

  return (
    <div>
      <h1>{asset.name}</h1>

      <AssetProfilePhoto asset={asset} />

      <form className="asset-edit-form" onSubmit={handleSubmit}>
        <label>
          Name
          <input value={form.name ?? ""} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </label>
        <label>
          Notes
          <textarea value={form.notes ?? ""} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </label>

        {asset.asset_type === "vehicle" && (
          <fieldset>
            <legend>Vehicle details</legend>
            <label>
              Make
              <input
                value={form.vehicle_details?.make ?? ""}
                onChange={(e) =>
                  setForm({ ...form, vehicle_details: { ...form.vehicle_details, make: e.target.value } })
                }
              />
            </label>
            <label>
              Model
              <input
                value={form.vehicle_details?.model ?? ""}
                onChange={(e) =>
                  setForm({ ...form, vehicle_details: { ...form.vehicle_details, model: e.target.value } })
                }
              />
            </label>
            <label>
              Year
              <input
                type="number"
                value={form.vehicle_details?.year ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    vehicle_details: {
                      ...form.vehicle_details,
                      year: e.target.value ? Number(e.target.value) : null,
                    },
                  })
                }
              />
            </label>
            <label>
              Current mileage
              <input
                type="number"
                value={form.vehicle_details?.current_mileage ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    vehicle_details: {
                      ...form.vehicle_details,
                      current_mileage: e.target.value ? Number(e.target.value) : null,
                    },
                  })
                }
              />
            </label>
          </fieldset>
        )}

        {asset.asset_type === "equipment" && (
          <fieldset>
            <legend>Equipment details</legend>
            <label>
              Manufacturer
              <input
                value={form.equipment_details?.manufacturer ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    equipment_details: { ...form.equipment_details, manufacturer: e.target.value },
                  })
                }
              />
            </label>
            <label>
              Model number
              <input
                value={form.equipment_details?.model_number ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    equipment_details: { ...form.equipment_details, model_number: e.target.value },
                  })
                }
              />
            </label>
          </fieldset>
        )}

        {(asset.asset_type === "property" || asset.asset_type === "home_system") && (
          <fieldset>
            <legend>Property details</legend>
            <label>
              Address
              <input
                value={form.property_details?.address ?? ""}
                onChange={(e) =>
                  setForm({ ...form, property_details: { ...form.property_details, address: e.target.value } })
                }
              />
            </label>
          </fieldset>
        )}

        <div className="form-actions">
          <button type="submit" disabled={saveMutation.isPending}>
            Save
          </button>
          <button type="button" className="danger" onClick={() => deleteMutation.mutate()}>
            Delete asset
          </button>
        </div>
      </form>

      <MaintenanceRecordsSection assetId={asset.id} />
      <SchedulesSection assetId={asset.id} />
    </div>
  );
}
