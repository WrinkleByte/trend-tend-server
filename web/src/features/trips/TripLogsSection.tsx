import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createTripLog, deleteTripLog, listTripLogs } from "../../api/tripLogs";
import type { TripPurpose } from "../../api/types";
import { AttachmentsSection } from "../attachments/AttachmentsSection";

// Fixed set plus free text — same pattern as maintenance record
// category/custom_category. See TripLogInput.kt in tendfida-mobile's
// shared module for where this set is canonically defined.
const PURPOSES: TripPurpose[] = ["business", "personal", "medical", "charity", "commute", "other"];

function purposeLabel(purpose: TripPurpose, customPurpose: string | null): string {
  if (purpose === "other" && customPurpose) return customPurpose;
  return purpose;
}

export function TripLogsSection({ assetId }: { assetId: string }) {
  const queryClient = useQueryClient();
  const { data: trips, isLoading } = useQuery({
    queryKey: ["trip-logs", assetId],
    queryFn: () => listTripLogs(assetId),
  });

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [performedAt, setPerformedAt] = useState(() => new Date().toISOString().slice(0, 10));
  const [purpose, setPurpose] = useState<TripPurpose>(PURPOSES[0]);
  const [customPurpose, setCustomPurpose] = useState("");
  const [startOdometer, setStartOdometer] = useState("");
  const [endOdometer, setEndOdometer] = useState("");
  const [distance, setDistance] = useState("");
  const [distanceTouched, setDistanceTouched] = useState(false);
  const [notes, setNotes] = useState("");

  // Distance auto-fills from odometer readings when both are present —
  // per TripLogInput.kt's doc comment, distance is normally derived this
  // way, entered directly only when odometer readings aren't tracked.
  // Once the admin edits distance by hand, stop overwriting it.
  function applyOdometer(start: string, end: string) {
    setStartOdometer(start);
    setEndOdometer(end);
    if (!distanceTouched && start && end) {
      const computed = Number(end) - Number(start);
      if (!Number.isNaN(computed) && computed >= 0) setDistance(String(computed));
    }
  }

  const createMutation = useMutation({
    mutationFn: () =>
      createTripLog({
        asset_id: assetId,
        performed_at: performedAt,
        purpose,
        custom_purpose: purpose === "other" ? customPurpose || null : null,
        start_odometer: startOdometer || null,
        end_odometer: endOdometer,
        distance,
        notes: notes || null,
      }),
    onSuccess: () => {
      setCustomPurpose("");
      setStartOdometer("");
      setEndOdometer("");
      setDistance("");
      setDistanceTouched(false);
      setNotes("");
      queryClient.invalidateQueries({ queryKey: ["trip-logs", assetId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (tripId: string) => deleteTripLog(tripId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trip-logs", assetId] }),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (endOdometer && distance) createMutation.mutate();
  }

  return (
    <section>
      <h2>Trip log</h2>
      <form className="inline-form" onSubmit={handleSubmit}>
        <input type="date" value={performedAt} onChange={(e) => setPerformedAt(e.target.value)} required />
        <select value={purpose} onChange={(e) => setPurpose(e.target.value as TripPurpose)}>
          {PURPOSES.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        {purpose === "other" && (
          <input
            placeholder="Purpose"
            value={customPurpose}
            onChange={(e) => setCustomPurpose(e.target.value)}
          />
        )}
        <input
          type="number"
          step="0.1"
          placeholder="Start odometer"
          value={startOdometer}
          onChange={(e) => applyOdometer(e.target.value, endOdometer)}
        />
        <input
          type="number"
          step="0.1"
          placeholder="End odometer"
          value={endOdometer}
          onChange={(e) => applyOdometer(startOdometer, e.target.value)}
          required
        />
        <input
          type="number"
          step="0.1"
          placeholder="Distance"
          value={distance}
          onChange={(e) => {
            setDistanceTouched(true);
            setDistance(e.target.value);
          }}
          required
        />
        <input placeholder="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
        <button type="submit" disabled={createMutation.isPending}>
          Add trip
        </button>
      </form>

      {isLoading && <p>Loading…</p>}
      <ul className="record-list">
        {trips?.map((trip) => (
          <li key={trip.id}>
            <div className="record-row">
              <span className="record-date">{trip.performed_at.slice(0, 10)}</span>
              <span className="record-category">{purposeLabel(trip.purpose, trip.custom_purpose)}</span>
              <span className="record-description">{trip.notes || "—"}</span>
              <span className="record-cost">{trip.distance} mi</span>
              <div className="record-actions">
                <button type="button" onClick={() => setExpandedId(expandedId === trip.id ? null : trip.id)}>
                  {expandedId === trip.id ? "Hide receipts" : "Receipts"}
                </button>
                <button type="button" className="danger" onClick={() => deleteMutation.mutate(trip.id)}>
                  Delete
                </button>
              </div>
            </div>
            {expandedId === trip.id && <AttachmentsSection entityType="trip_log" entityId={trip.id} />}
          </li>
        ))}
      </ul>
      {trips?.length === 0 && <p>No trips logged yet.</p>}
    </section>
  );
}
