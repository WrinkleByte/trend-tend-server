import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFuelLog, deleteFuelLog, listFuelLogs, updateFuelLog } from "../../api/fuelLogs";
import type { FuelLog } from "../../api/types";
import { AttachmentsSection } from "../attachments/AttachmentsSection";
import { GridField } from "../../components/GridField";

// Keeps the quick-add inline form to the fields people actually fill in at
// the pump -- octane/cetane/gas_brand/location/additive/mpg/cost_per_gallon
// all exist on the backend schema and sync down from mobile, but stay out
// of the quick-add form's scope (same choice MaintenanceRecordsSection's
// add form makes). The edit form below is different: it exposes every
// field FuelLogUpdate tracks (Vikunja #111), since editing an existing
// entry is exactly where those mobile-only fields need a web entry point.
export function FuelLogsSection({ assetId }: { assetId: string }) {
  const queryClient = useQueryClient();
  const { data: logs, isLoading } = useQuery({
    queryKey: ["fuel-logs", assetId],
    queryFn: () => listFuelLogs(assetId),
  });

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [performedAt, setPerformedAt] = useState(() => new Date().toISOString().slice(0, 10));
  const [odometerReading, setOdometerReading] = useState("");
  const [gallons, setGallons] = useState("");
  const [totalCost, setTotalCost] = useState("");
  const [isFillUp, setIsFillUp] = useState(true);

  // Edit-in-place state (Vikunja #111) -- only one row editable at a time.
  // Exposes every field FuelLogUpdate tracks, not just the quick-add form's
  // subset -- see this file's top comment.
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editPerformedAt, setEditPerformedAt] = useState("");
  const [editOdometerReading, setEditOdometerReading] = useState("");
  const [editGallons, setEditGallons] = useState("");
  const [editCostPerGallon, setEditCostPerGallon] = useState("");
  const [editTotalCost, setEditTotalCost] = useState("");
  const [editIsFillUp, setEditIsFillUp] = useState(true);
  const [editMpg, setEditMpg] = useState("");
  const [editOctane, setEditOctane] = useState("");
  const [editCetane, setEditCetane] = useState("");
  const [editGasBrand, setEditGasBrand] = useState("");
  const [editLocation, setEditLocation] = useState("");
  const [editAdditive, setEditAdditive] = useState("");
  const [editNotes, setEditNotes] = useState("");

  function startEdit(log: FuelLog) {
    setEditingId(log.id);
    setEditPerformedAt(log.performed_at.slice(0, 10));
    setEditOdometerReading(log.odometer_reading != null ? String(log.odometer_reading) : "");
    setEditGallons(log.gallons);
    setEditCostPerGallon(log.cost_per_gallon ?? "");
    setEditTotalCost(log.total_cost ?? "");
    setEditIsFillUp(log.is_fill_up);
    setEditMpg(log.mpg ?? "");
    setEditOctane(log.octane != null ? String(log.octane) : "");
    setEditCetane(log.cetane != null ? String(log.cetane) : "");
    setEditGasBrand(log.gas_brand ?? "");
    setEditLocation(log.location ?? "");
    setEditAdditive(log.additive ?? "");
    setEditNotes(log.notes ?? "");
  }

  const updateMutation = useMutation({
    mutationFn: (id: string) =>
      updateFuelLog(id, {
        performed_at: editPerformedAt,
        odometer_reading: editOdometerReading ? Number(editOdometerReading) : null,
        gallons: editGallons,
        cost_per_gallon: editCostPerGallon || null,
        total_cost: editTotalCost || null,
        is_fill_up: editIsFillUp,
        mpg: editMpg || null,
        octane: editOctane ? Number(editOctane) : null,
        cetane: editCetane ? Number(editCetane) : null,
        gas_brand: editGasBrand || null,
        location: editLocation || null,
        additive: editAdditive || null,
        notes: editNotes || null,
      }),
    onSuccess: () => {
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["fuel-logs", assetId] });
    },
  });

  function handleEditSubmit(event: FormEvent, id: string) {
    event.preventDefault();
    if (editGallons) updateMutation.mutate(id);
  }

  const createMutation = useMutation({
    mutationFn: () =>
      createFuelLog({
        asset_id: assetId,
        performed_at: performedAt,
        odometer_reading: odometerReading ? Number(odometerReading) : null,
        gallons,
        total_cost: totalCost || null,
        is_fill_up: isFillUp,
      }),
    onSuccess: () => {
      setOdometerReading("");
      setGallons("");
      setTotalCost("");
      setIsFillUp(true);
      queryClient.invalidateQueries({ queryKey: ["fuel-logs", assetId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteFuelLog(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["fuel-logs", assetId] }),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (gallons) createMutation.mutate();
  }

  // Mirrors AssetDetailPage.tsx's confirm() guard (Vikunja #34) -- extended
  // to fuel/service/trip records per explicit follow-up request rather than
  // left as a latent gap like the other unguarded deletes in this app.
  function handleDelete(logId: string, performedAt: string) {
    if (window.confirm(`Permanently delete the fuel-up from ${performedAt.slice(0, 10)}? This cannot be undone.`)) {
      deleteMutation.mutate(logId);
    }
  }

  return (
    <section>
      <h2>Fuel log</h2>
      <form className="inline-form" onSubmit={handleSubmit}>
        <input type="date" value={performedAt} onChange={(e) => setPerformedAt(e.target.value)} required />
        <input
          type="number"
          step="0.1"
          placeholder="Odometer"
          value={odometerReading}
          onChange={(e) => setOdometerReading(e.target.value)}
        />
        <input
          type="number"
          step="0.001"
          placeholder="Gallons"
          value={gallons}
          onChange={(e) => setGallons(e.target.value)}
          required
        />
        <input
          type="number"
          step="0.01"
          placeholder="Total cost"
          value={totalCost}
          onChange={(e) => setTotalCost(e.target.value)}
        />
        <label className="check-label" style={{ marginBottom: 0 }}>
          <input type="checkbox" checked={isFillUp} onChange={(e) => setIsFillUp(e.target.checked)} />
          Full tank
        </label>
        <button type="submit" disabled={createMutation.isPending}>
          Add fuel-up
        </button>
      </form>

      {isLoading && <p>Loading…</p>}
      <ul className="record-list">
        {logs?.map((log) =>
          editingId === log.id ? (
            <li key={log.id}>
              <form className="record-edit-form" onSubmit={(e) => handleEditSubmit(e, log.id)}>
                <div className="field-grid field-compact">
                  <GridField label="Date" type="date" value={editPerformedAt} onChange={setEditPerformedAt} />
                  <GridField
                    label="Odometer"
                    type="number"
                    step="0.1"
                    value={editOdometerReading}
                    onChange={setEditOdometerReading}
                  />
                  <GridField
                    label="Gallons"
                    type="number"
                    step="0.001"
                    value={editGallons}
                    onChange={setEditGallons}
                  />
                  <GridField
                    label="Cost per gallon"
                    type="number"
                    step="0.001"
                    value={editCostPerGallon}
                    onChange={setEditCostPerGallon}
                  />
                  <GridField
                    label="Total cost"
                    type="number"
                    step="0.01"
                    value={editTotalCost}
                    onChange={setEditTotalCost}
                  />
                  <GridField label="MPG" type="number" step="0.1" value={editMpg} onChange={setEditMpg} />
                  <GridField label="Octane" type="number" value={editOctane} onChange={setEditOctane} />
                  <GridField label="Cetane" type="number" value={editCetane} onChange={setEditCetane} />
                  <GridField label="Gas brand" value={editGasBrand} onChange={setEditGasBrand} />
                  <GridField label="Location" value={editLocation} onChange={setEditLocation} />
                  <GridField label="Additive" value={editAdditive} onChange={setEditAdditive} />
                  <label className="check-label">
                    <input
                      type="checkbox"
                      checked={editIsFillUp}
                      onChange={(e) => setEditIsFillUp(e.target.checked)}
                    />
                    Full tank
                  </label>
                  <div className="field-full form-field">
                    <label htmlFor="fuel-edit-notes">Notes</label>
                    <textarea
                      id="fuel-edit-notes"
                      rows={2}
                      value={editNotes}
                      onChange={(e) => setEditNotes(e.target.value)}
                    />
                  </div>
                </div>
                <div className="form-actions" style={{ marginTop: 12 }}>
                  <button type="submit" disabled={updateMutation.isPending}>
                    Save
                  </button>
                  <button type="button" className="secondary" onClick={() => setEditingId(null)}>
                    Cancel
                  </button>
                </div>
              </form>
            </li>
          ) : (
            <li key={log.id}>
              <div className="record-row">
                <span className="record-date">{log.performed_at.slice(0, 10)}</span>
                <span className="record-category">{log.is_fill_up ? "full tank" : "partial"}</span>
                <span className="record-description">
                  {log.gallons} gal
                  {log.odometer_reading != null ? ` at ${log.odometer_reading.toLocaleString()}` : ""}
                  {log.gas_brand ? ` • ${log.gas_brand}` : ""}
                  {log.location ? ` • ${log.location}` : ""}
                </span>
                <span className="record-cost">{log.total_cost != null ? `$${log.total_cost}` : ""}</span>
                <div className="record-actions">
                  <button type="button" onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}>
                    {expandedId === log.id ? "Hide receipts" : "Receipts"}
                  </button>
                  <button type="button" onClick={() => startEdit(log)}>
                    Edit
                  </button>
                  <button type="button" className="danger" onClick={() => handleDelete(log.id, log.performed_at)}>
                    Delete
                  </button>
                </div>
              </div>
              {/* notes/gas_brand/location/octane/cetane/additive/mpg all sync down from
                  mobile (the only place they're currently editable, see this file's top
                  comment) but were never rendered anywhere here -- Vikunja #99. */}
              {log.notes && <div className="record-notes">{log.notes}</div>}
              {expandedId === log.id && <AttachmentsSection entityType="fuel_log" entityId={log.id} />}
            </li>
          ),
        )}
      </ul>
      {logs?.length === 0 && <p>No fuel-ups logged yet.</p>}
    </section>
  );
}
