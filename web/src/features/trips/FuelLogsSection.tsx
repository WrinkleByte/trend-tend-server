import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFuelLog, deleteFuelLog, listFuelLogs } from "../../api/fuelLogs";

// Keeps the inline form to the fields people actually fill in at the pump —
// octane/cetane/gas_brand/location/additive/mpg all exist on the backend
// schema but stay editable only via a future dedicated edit view, same
// scoping choice MaintenanceRecordsSection makes (e.g. performed_by isn't
// in its inline form either).
export function FuelLogsSection({ assetId }: { assetId: string }) {
  const queryClient = useQueryClient();
  const { data: logs, isLoading } = useQuery({
    queryKey: ["fuel-logs", assetId],
    queryFn: () => listFuelLogs(assetId),
  });

  const [performedAt, setPerformedAt] = useState(() => new Date().toISOString().slice(0, 10));
  const [odometerReading, setOdometerReading] = useState("");
  const [gallons, setGallons] = useState("");
  const [totalCost, setTotalCost] = useState("");
  const [isFillUp, setIsFillUp] = useState(true);

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
        {logs?.map((log) => (
          <li key={log.id}>
            <div className="record-row">
              <span className="record-date">{log.performed_at.slice(0, 10)}</span>
              <span className="record-category">{log.is_fill_up ? "full tank" : "partial"}</span>
              <span className="record-description">
                {log.gallons} gal{log.odometer_reading != null ? ` at ${log.odometer_reading.toLocaleString()}` : ""}
              </span>
              <span className="record-cost">{log.total_cost != null ? `$${log.total_cost}` : ""}</span>
              <div className="record-actions">
                <button type="button" className="danger" onClick={() => deleteMutation.mutate(log.id)}>
                  Delete
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
      {logs?.length === 0 && <p>No fuel-ups logged yet.</p>}
    </section>
  );
}
