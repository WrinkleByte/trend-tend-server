import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createMaintenanceSchedule,
  deleteMaintenanceSchedule,
  listMaintenanceSchedules,
  updateMaintenanceSchedule,
} from "../../api/maintenanceSchedules";
import type { IntervalType, MaintenanceSchedule } from "../../api/types";

export function SchedulesSection({ assetId }: { assetId: string }) {
  const queryClient = useQueryClient();
  const { data: schedules, isLoading } = useQuery({
    queryKey: ["maintenance-schedules", assetId],
    queryFn: () => listMaintenanceSchedules(assetId),
  });

  const [name, setName] = useState("");
  const [intervalType, setIntervalType] = useState<IntervalType>("time");
  const [intervalDays, setIntervalDays] = useState("90");
  const [intervalUsageAmount, setIntervalUsageAmount] = useState("3000");

  // Edit-in-place state (Vikunja #111) -- only one row editable at a time,
  // mirrors FuelLogsSection.tsx's identical pattern. interval_type itself
  // isn't editable (MaintenanceScheduleUpdate has no such field -- changing
  // time-based vs. usage-based vs. both is a different-enough schedule that
  // it's created fresh instead), so the edit form keeps the original
  // schedule's interval_type and only shows the day/usage fields it implies.
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editIntervalType, setEditIntervalType] = useState<IntervalType>("time");
  const [editIntervalDays, setEditIntervalDays] = useState("");
  const [editIntervalUsageAmount, setEditIntervalUsageAmount] = useState("");

  function startEdit(schedule: MaintenanceSchedule) {
    setEditingId(schedule.id);
    setEditName(schedule.name);
    setEditIntervalType(schedule.interval_type);
    setEditIntervalDays(schedule.interval_days != null ? String(schedule.interval_days) : "");
    setEditIntervalUsageAmount(
      schedule.interval_usage_amount != null ? String(schedule.interval_usage_amount) : "",
    );
  }

  const updateMutation = useMutation({
    mutationFn: (id: string) =>
      updateMaintenanceSchedule(id, {
        name: editName,
        interval_days: editIntervalType !== "usage" ? Number(editIntervalDays) : null,
        interval_usage_amount: editIntervalType !== "time" ? Number(editIntervalUsageAmount) : null,
      }),
    onSuccess: () => {
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["maintenance-schedules", assetId] });
    },
  });

  function handleEditSubmit(event: FormEvent, id: string) {
    event.preventDefault();
    if (editName.trim()) updateMutation.mutate(id);
  }

  const createMutation = useMutation({
    mutationFn: () =>
      createMaintenanceSchedule({
        asset_id: assetId,
        name,
        interval_type: intervalType,
        interval_days: intervalType !== "usage" ? Number(intervalDays) : null,
        interval_usage_amount: intervalType !== "time" ? Number(intervalUsageAmount) : null,
        // "current_mileage" is the only usage field the recurrence engine
        // currently reads (see backend/app/api/v1/maintenance_schedules.py).
        usage_field: intervalType !== "time" ? "current_mileage" : null,
        anchor_date: new Date().toISOString().slice(0, 10),
      }),
    onSuccess: () => {
      setName("");
      queryClient.invalidateQueries({ queryKey: ["maintenance-schedules", assetId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteMaintenanceSchedule(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["maintenance-schedules", assetId] }),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (name.trim()) createMutation.mutate();
  }

  return (
    <section>
      <h2>Reminders</h2>
      <form className="inline-form" onSubmit={handleSubmit}>
        <input placeholder="e.g. Oil change" value={name} onChange={(e) => setName(e.target.value)} />
        <select value={intervalType} onChange={(e) => setIntervalType(e.target.value as IntervalType)}>
          <option value="time">Time-based</option>
          <option value="usage">Usage-based (mileage)</option>
          <option value="both">Both</option>
        </select>
        {intervalType !== "usage" && (
          <input
            type="number"
            value={intervalDays}
            onChange={(e) => setIntervalDays(e.target.value)}
            title="Repeat every N days"
          />
        )}
        {intervalType !== "time" && (
          <input
            type="number"
            value={intervalUsageAmount}
            onChange={(e) => setIntervalUsageAmount(e.target.value)}
            title="Repeat every N miles"
          />
        )}
        <button type="submit" disabled={createMutation.isPending}>
          Add reminder
        </button>
      </form>

      {isLoading && <p>Loading…</p>}
      <ul className="schedule-list">
        {schedules?.map((schedule) =>
          editingId === schedule.id ? (
            <li key={schedule.id}>
              <form className="inline-form" onSubmit={(e) => handleEditSubmit(e, schedule.id)}>
                <input placeholder="e.g. Oil change" value={editName} onChange={(e) => setEditName(e.target.value)} />
                {editIntervalType !== "usage" && (
                  <input
                    type="number"
                    value={editIntervalDays}
                    onChange={(e) => setEditIntervalDays(e.target.value)}
                    title="Repeat every N days"
                  />
                )}
                {editIntervalType !== "time" && (
                  <input
                    type="number"
                    value={editIntervalUsageAmount}
                    onChange={(e) => setEditIntervalUsageAmount(e.target.value)}
                    title="Repeat every N miles"
                  />
                )}
                <button type="submit" disabled={updateMutation.isPending}>
                  Save
                </button>
                <button type="button" className="secondary" onClick={() => setEditingId(null)}>
                  Cancel
                </button>
              </form>
            </li>
          ) : (
            <li key={schedule.id} className={schedule.is_overdue ? "overdue" : ""}>
              <span>{schedule.name}</span>
              <span>{schedule.next_due_date ? `Due ${schedule.next_due_date}` : "No due date yet"}</span>
              {schedule.is_overdue && <span className="badge">Overdue</span>}
              <button type="button" onClick={() => startEdit(schedule)}>
                Edit
              </button>
              <button type="button" className="danger" onClick={() => deleteMutation.mutate(schedule.id)}>
                Delete
              </button>
            </li>
          ),
        )}
      </ul>
      {schedules?.length === 0 && <p>No reminders set.</p>}
    </section>
  );
}
