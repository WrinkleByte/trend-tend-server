import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createMaintenanceRecord,
  deleteMaintenanceRecord,
  listMaintenanceRecords,
  updateMaintenanceRecord,
} from "../../api/maintenanceRecords";
import { listMaintenanceSchedules, updateMaintenanceSchedule } from "../../api/maintenanceSchedules";
import { RECORD_CATEGORIES as CATEGORIES, recordMatchesSchedule } from "../schedules/maintenanceAlerts";
import type { MaintenanceRecord, MaintenanceSchedule } from "../../api/types";
import { AttachmentsSection } from "../attachments/AttachmentsSection";

export function MaintenanceRecordsSection({ assetId }: { assetId: string }) {
  const queryClient = useQueryClient();
  const { data: records, isLoading } = useQuery({
    queryKey: ["maintenance-records", assetId],
    queryFn: () => listMaintenanceRecords(assetId),
  });
  // Same query key MaintenanceAlertsSection.tsx uses -- shares its cache.
  // Needed here only to check for a matching active schedule right after a
  // record is created; the section itself has no schedule UI of its own.
  const { data: schedules } = useQuery({
    queryKey: ["maintenance-schedules", assetId],
    queryFn: () => listMaintenanceSchedules(assetId),
  });
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const [performedAt, setPerformedAt] = useState(() => new Date().toISOString().slice(0, 10));
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [description, setDescription] = useState("");
  const [cost, setCost] = useState("");

  // Edit-in-place state (Vikunja #111) -- only one row editable at a time,
  // mirrors FuelLogsSection.tsx's identical pattern.
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editPerformedAt, setEditPerformedAt] = useState("");
  const [editCategory, setEditCategory] = useState(CATEGORIES[0]);
  const [editDescription, setEditDescription] = useState("");
  const [editCost, setEditCost] = useState("");

  function startEdit(record: MaintenanceRecord) {
    setEditingId(record.id);
    setEditPerformedAt(record.performed_at.slice(0, 10));
    setEditCategory(record.category);
    setEditDescription(record.description ?? "");
    setEditCost(record.cost ?? "");
  }

  const updateRecordMutation = useMutation({
    mutationFn: (id: string) =>
      updateMaintenanceRecord(id, {
        performed_at: editPerformedAt,
        category: editCategory,
        description: editDescription || null,
        cost: editCost ? Number(editCost) : null,
      }),
    onSuccess: () => {
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["maintenance-records", assetId] });
    },
  });

  function handleEditSubmit(event: FormEvent, id: string) {
    event.preventDefault();
    updateRecordMutation.mutate(id);
  }

  // Vikunja #110: after a manually-added record, check for an active
  // schedule whose name matches its category and offer to clear it too --
  // mirrors mobile's ScheduleMatchConfirmationView (getActiveSchedulesForCategorySync),
  // including its "list every match individually, default all selected"
  // handling of duplicate same-name schedules.
  const [pendingMatch, setPendingMatch] = useState<{
    record: MaintenanceRecord;
    schedules: MaintenanceSchedule[];
    selected: Set<string>;
  } | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      createMaintenanceRecord({
        asset_id: assetId,
        performed_at: performedAt,
        category,
        description: description || null,
        cost: cost ? Number(cost) : null,
      }),
    onSuccess: (record) => {
      setDescription("");
      setCost("");
      queryClient.invalidateQueries({ queryKey: ["maintenance-records", assetId] });

      const matches = (schedules ?? []).filter((s) => s.active && recordMatchesSchedule(record, s.name));
      if (matches.length > 0) {
        setPendingMatch({ record, schedules: matches, selected: new Set(matches.map((s) => s.id)) });
      }
    },
  });

  const clearMatchingSchedulesMutation = useMutation({
    mutationFn: async () => {
      if (!pendingMatch) return;
      const toClear = pendingMatch.schedules.filter((s) => pendingMatch.selected.has(s.id));
      await Promise.all(
        toClear.map((s) =>
          updateMaintenanceSchedule(s.id, {
            anchor_date: pendingMatch.record.performed_at,
            anchor_usage_value: pendingMatch.record.odometer_reading,
            dismissed_at: null,
          }),
        ),
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["maintenance-schedules", assetId] });
      setPendingMatch(null);
    },
  });

  function toggleMatchSelected(scheduleId: string) {
    setPendingMatch((prev) => {
      if (!prev) return prev;
      const selected = new Set(prev.selected);
      if (selected.has(scheduleId)) selected.delete(scheduleId);
      else selected.add(scheduleId);
      return { ...prev, selected };
    });
  }

  const deleteMutation = useMutation({
    mutationFn: (recordId: string) => deleteMaintenanceRecord(recordId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["maintenance-records", assetId] }),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate();
  }

  // Mirrors AssetDetailPage.tsx's confirm() guard (Vikunja #34) -- extended
  // to fuel/service/trip records per explicit follow-up request rather than
  // left as a latent gap like the other unguarded deletes in this app. This
  // is the exact entity type that prompted the follow-up (an accidental
  // single-click delete on this same section).
  function handleDelete(recordId: string, performedAt: string, category: string) {
    const label = category.replace("_", " ");
    if (window.confirm(`Permanently delete this ${label} record from ${performedAt.slice(0, 10)}? This cannot be undone.`)) {
      deleteMutation.mutate(recordId);
    }
  }

  return (
    <section>
      <h2>Service history</h2>
      <form className="inline-form" onSubmit={handleSubmit}>
        <input type="date" value={performedAt} onChange={(e) => setPerformedAt(e.target.value)} required />
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c.replace("_", " ")}
            </option>
          ))}
        </select>
        <input placeholder="Description" value={description} onChange={(e) => setDescription(e.target.value)} />
        <input
          type="number"
          step="0.01"
          placeholder="Cost"
          value={cost}
          onChange={(e) => setCost(e.target.value)}
        />
        <button type="submit" disabled={createMutation.isPending}>
          Add record
        </button>
      </form>

      {pendingMatch && (
        <div className="schedule-match-prompt">
          <p>
            This matches {pendingMatch.schedules.length === 1 ? "an active reminder" : "active reminders"} for this
            asset. Clear it too?
          </p>
          <ul>
            {pendingMatch.schedules.map((s) => (
              <li key={s.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={pendingMatch.selected.has(s.id)}
                    onChange={() => toggleMatchSelected(s.id)}
                  />
                  {s.name}
                  {s.next_due_date ? ` (due ${s.next_due_date})` : ""}
                </label>
              </li>
            ))}
          </ul>
          <div className="schedule-match-actions">
            <button
              type="button"
              onClick={() => clearMatchingSchedulesMutation.mutate()}
              disabled={clearMatchingSchedulesMutation.isPending || pendingMatch.selected.size === 0}
            >
              Confirm
            </button>
            <button type="button" onClick={() => setPendingMatch(null)}>
              Skip
            </button>
          </div>
        </div>
      )}

      {isLoading && <p>Loading…</p>}
      <ul className="record-list">
        {records?.map((record) =>
          editingId === record.id ? (
            <li key={record.id}>
              <form className="inline-form" onSubmit={(e) => handleEditSubmit(e, record.id)}>
                <input
                  type="date"
                  value={editPerformedAt}
                  onChange={(e) => setEditPerformedAt(e.target.value)}
                  required
                />
                <select value={editCategory} onChange={(e) => setEditCategory(e.target.value)}>
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c.replace("_", " ")}
                    </option>
                  ))}
                </select>
                <input
                  placeholder="Description"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                />
                <input
                  type="number"
                  step="0.01"
                  placeholder="Cost"
                  value={editCost}
                  onChange={(e) => setEditCost(e.target.value)}
                />
                <button type="submit" disabled={updateRecordMutation.isPending}>
                  Save
                </button>
                <button type="button" className="secondary" onClick={() => setEditingId(null)}>
                  Cancel
                </button>
              </form>
            </li>
          ) : (
            <li key={record.id}>
              <div className="record-row">
                <span className="record-date">{record.performed_at}</span>
                <span className="record-category">{record.category.replace("_", " ")}</span>
                <span className="record-description">{record.description || "—"}</span>
                <span className="record-cost">{record.cost != null ? `$${record.cost}` : ""}</span>
                <div className="record-actions">
                  <button type="button" onClick={() => setExpandedId(expandedId === record.id ? null : record.id)}>
                    {expandedId === record.id ? "Hide receipts" : "Receipts"}
                  </button>
                  <button type="button" onClick={() => startEdit(record)}>
                    Edit
                  </button>
                  <button
                    type="button"
                    className="danger"
                    onClick={() => handleDelete(record.id, record.performed_at, record.category)}
                  >
                    Delete
                  </button>
                </div>
              </div>
              {expandedId === record.id && <AttachmentsSection entityType="record" entityId={record.id} />}
            </li>
          ),
        )}
      </ul>
      {records?.length === 0 && <p>No service history yet.</p>}
    </section>
  );
}
