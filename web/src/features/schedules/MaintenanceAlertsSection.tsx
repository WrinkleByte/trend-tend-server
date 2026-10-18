import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listMaintenanceSchedules, updateMaintenanceSchedule } from "../../api/maintenanceSchedules";
import { createMaintenanceRecord, listMaintenanceRecords } from "../../api/maintenanceRecords";
import {
  categoriesForAssetType,
  displayCategory,
  computeAlerts,
  CUSTOM_CATEGORY_VALUE,
  normalizeForMatch,
  recordMatchesSchedule,
  type ScheduleAlert,
} from "./maintenanceAlerts";
import type { MaintenanceRecord } from "../../api/types";
import { WHOLE_NUMBER_INPUT } from "../../components/wholeNumberInput";

type ExpandedMode = "perform" | "existing";

/** A schedule's `name` is free text on web -- best-effort match it against
 * the asset-type-appropriate fixed category set (e.g. "Oil Change" ->
 * "oil_change"); falls back to the "custom" sentinel + the schedule's own
 * name as the custom category when nothing matches, so "Mark as Performed"
 * always produces a sensible record even for a schedule named something
 * that set doesn't cover. */
function bestGuessCategory(scheduleName: string, assetType: string): { category: string; customCategory: string | null } {
  const normalized = normalizeForMatch(scheduleName);
  const match = categoriesForAssetType(assetType).find((c) => normalizeForMatch(c) === normalized);
  return match
    ? { category: match, customCategory: null }
    : { category: CUSTOM_CATEGORY_VALUE, customCategory: scheduleName };
}

function dueText(alert: ScheduleAlert): string {
  const parts: string[] = [];
  if (alert.daysUntilDue != null) {
    const d = alert.daysUntilDue;
    parts.push(d < 0 ? `Overdue by ${-d} day${-d === 1 ? "" : "s"}` : d === 0 ? "Due today" : `Due in ${d} day${d === 1 ? "" : "s"}`);
  }
  if (alert.usageUntilDue != null) {
    const u = alert.usageUntilDue;
    parts.push(u < 0 ? `Overdue by ${-u} mi` : `Due in ${u} mi`);
  }
  return parts.join(" · ");
}

export function MaintenanceAlertsSection({
  assetId,
  assetType,
  currentUsage,
}: {
  assetId: string;
  assetType: string;
  currentUsage: number | null;
}) {
  const queryClient = useQueryClient();
  const { data: schedules } = useQuery({
    queryKey: ["maintenance-schedules", assetId],
    queryFn: () => listMaintenanceSchedules(assetId),
  });
  // Same query key MaintenanceRecordsSection.tsx uses -- shares its cache,
  // no extra fetch just because this section also needs the record list
  // for "Select Existing".
  const { data: records } = useQuery({
    queryKey: ["maintenance-records", assetId],
    queryFn: () => listMaintenanceRecords(assetId),
  });

  const [expanded, setExpanded] = useState<{ scheduleId: string; mode: ExpandedMode } | null>(null);
  const [performedAt, setPerformedAt] = useState(() => new Date().toISOString().slice(0, 10));
  const [odometer, setOdometer] = useState("");

  function toggleExpand(scheduleId: string, mode: ExpandedMode) {
    setExpanded((prev) => {
      if (prev?.scheduleId === scheduleId && prev.mode === mode) return null;
      if (mode === "perform") {
        setPerformedAt(new Date().toISOString().slice(0, 10));
        setOdometer("");
      }
      return { scheduleId, mode };
    });
  }

  function invalidateSchedules() {
    queryClient.invalidateQueries({ queryKey: ["maintenance-schedules", assetId] });
  }

  const dismissMutation = useMutation({
    mutationFn: (scheduleId: string) =>
      updateMaintenanceSchedule(scheduleId, { dismissed_at: new Date().toISOString() }),
    onSuccess: invalidateSchedules,
  });

  // Mirrors MaintenanceScheduleRepository.markPerformed's actual writes
  // (tendfida-mobile) -- anchor_date/anchor_usage_value roll forward to the
  // picked record, dismissed_at clears. lastCompletedRecordId is
  // deliberately not ported: mobile's own doc comment calls it "mobile-only
  // bookkeeping," never synced.
  const clearViaExistingMutation = useMutation({
    mutationFn: ({ scheduleId, record }: { scheduleId: string; record: MaintenanceRecord }) =>
      updateMaintenanceSchedule(scheduleId, {
        anchor_date: record.performed_at,
        anchor_usage_value: record.odometer_reading,
        dismissed_at: null,
      }),
    onSuccess: () => {
      invalidateSchedules();
      setExpanded(null);
    },
  });

  const markPerformedMutation = useMutation({
    mutationFn: async (schedule: ScheduleAlert["schedule"]) => {
      const { category, customCategory } = bestGuessCategory(schedule.name, assetType);
      const odometerReading = odometer ? Number(odometer) : null;
      await createMaintenanceRecord({
        asset_id: assetId,
        performed_at: performedAt,
        category,
        custom_category: customCategory,
        odometer_reading: odometerReading,
        schedule_id: schedule.id,
      });
      // Linking schedule_id on the record is just historical bookkeeping --
      // the schedule's own due date only advances via this explicit PATCH
      // (there's no backend hook that rolls it forward automatically from
      // the record's schedule_id foreign key), same as
      // clearViaExistingMutation above and mobile's markPerformed.
      await updateMaintenanceSchedule(schedule.id, {
        anchor_date: performedAt,
        anchor_usage_value: odometerReading,
        dismissed_at: null,
      });
    },
    onSuccess: () => {
      invalidateSchedules();
      queryClient.invalidateQueries({ queryKey: ["maintenance-records", assetId] });
      setExpanded(null);
      setOdometer("");
    },
  });

  function handleMarkPerformed(event: FormEvent, schedule: ScheduleAlert["schedule"]) {
    event.preventDefault();
    markPerformedMutation.mutate(schedule);
  }

  const alerts = schedules ? computeAlerts(schedules, currentUsage) : [];

  return (
    <section>
      <h2>Alerts</h2>
      <ul className="alert-list">
        {alerts.map((alert) => {
          const schedule = alert.schedule;
          const isExpandedPerform = expanded?.scheduleId === schedule.id && expanded.mode === "perform";
          const isExpandedExisting = expanded?.scheduleId === schedule.id && expanded.mode === "existing";
          const matchingRecords = (records ?? [])
            .slice()
            .sort((a, b) => Number(recordMatchesSchedule(b, schedule.name)) - Number(recordMatchesSchedule(a, schedule.name)));

          return (
            <li key={schedule.id} className={alert.severity === "overdue" ? "overdue" : "due-soon"}>
              <div className="alert-row">
                <span className="alert-name">{schedule.name}</span>
                <span className="alert-due">{dueText(alert)}</span>
                <span className="badge">{alert.severity === "overdue" ? "Overdue" : "Due soon"}</span>
                <div className="alert-actions">
                  <button type="button" onClick={() => toggleExpand(schedule.id, "perform")}>
                    Mark as Performed
                  </button>
                  <button type="button" onClick={() => toggleExpand(schedule.id, "existing")}>
                    Select Existing
                  </button>
                  <button type="button" onClick={() => dismissMutation.mutate(schedule.id)} disabled={dismissMutation.isPending}>
                    Ignore
                  </button>
                </div>
              </div>

              {isExpandedPerform && (
                <form className="inline-form" onSubmit={(e) => handleMarkPerformed(e, schedule)}>
                  <input type="date" value={performedAt} onChange={(e) => setPerformedAt(e.target.value)} required />
                  <input
                    {...WHOLE_NUMBER_INPUT}
                    placeholder="Odometer (optional)"
                    value={odometer}
                    onChange={(e) => setOdometer(e.target.value)}
                  />
                  <button type="submit" disabled={markPerformedMutation.isPending}>
                    Save
                  </button>
                </form>
              )}

              {isExpandedExisting && (
                <ul className="record-list">
                  {matchingRecords.map((record) => (
                    <li key={record.id}>
                      <button
                        type="button"
                        onClick={() => clearViaExistingMutation.mutate({ scheduleId: schedule.id, record })}
                        disabled={clearViaExistingMutation.isPending}
                      >
                        {record.performed_at} — {displayCategory(record.category, record.custom_category)}
                        {record.description ? `: ${record.description}` : ""}
                      </button>
                    </li>
                  ))}
                  {matchingRecords.length === 0 && <p>No existing records for this asset yet.</p>}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
      {alerts.length === 0 && <p>No maintenance due right now.</p>}
    </section>
  );
}
