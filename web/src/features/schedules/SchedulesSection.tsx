import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createMaintenanceSchedule,
  deleteMaintenanceSchedule,
  listMaintenanceSchedules,
} from "../../api/maintenanceSchedules";
import type { IntervalType } from "../../api/types";

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
        {schedules?.map((schedule) => (
          <li key={schedule.id} className={schedule.is_overdue ? "overdue" : ""}>
            <span>{schedule.name}</span>
            <span>{schedule.next_due_date ? `Due ${schedule.next_due_date}` : "No due date yet"}</span>
            {schedule.is_overdue && <span className="badge">Overdue</span>}
            <button type="button" className="danger" onClick={() => deleteMutation.mutate(schedule.id)}>
              Delete
            </button>
          </li>
        ))}
      </ul>
      {schedules?.length === 0 && <p>No reminders set.</p>}
    </section>
  );
}
