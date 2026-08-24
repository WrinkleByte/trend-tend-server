import type { MaintenanceRecord, MaintenanceSchedule } from "../../api/types";

// Ports tendfida-mobile's shared/src/commonMain/kotlin/com/wrinklebyte/domain/MaintenanceAlertCalculator.kt.
// Hardcoded rather than a household/user setting -- there's no backend or
// per-household concept of a due-soon threshold at all today (confirmed via
// audit for Vikunja #110); matches mobile's own MaintenanceAlertDefaults.
export const DUE_SOON_DAYS = 14;
export const DUE_SOON_USAGE = 500;

// Record categories (MaintenanceRecordsSection.tsx's create-form select) --
// lives here, not in that component file, so exporting it doesn't trip
// react-refresh's "only export components" Fast Refresh rule.
export const RECORD_CATEGORIES = ["oil_change", "tires", "repair", "inspection", "cleaning", "filter", "other"];

export type AlertSeverity = "overdue" | "due_soon";

export interface ScheduleAlert {
  schedule: MaintenanceSchedule;
  severity: AlertSeverity;
  daysUntilDue: number | null;
  usageUntilDue: number | null;
}

/** Case-insensitive, underscore/space-insensitive comparison -- schedule
 * names are free text on web (unlike mobile's fixed-category-or-custom
 * split), while record categories are a fixed snake_case set
 * (MaintenanceRecordsSection.tsx's CATEGORIES). A schedule named "Oil
 * Change" needs to match a record with category "oil_change". */
export function normalizeForMatch(value: string): string {
  return value.trim().toLowerCase().replace(/_/g, " ");
}

/** Mirrors getActiveSchedulesForCategorySync's case-insensitive name match
 * (tendfida-mobile) -- used both when marking an alert performed (does
 * this existing record match this schedule?) and when creating a new
 * record (does it match any active schedule, so we can offer to clear
 * one?). Checks `custom_category` too, for a record filed under "other". */
export function recordMatchesSchedule(record: MaintenanceRecord, scheduleName: string): boolean {
  const normalized = normalizeForMatch(scheduleName);
  return (
    normalizeForMatch(record.category) === normalized ||
    (record.custom_category != null && normalizeForMatch(record.custom_category) === normalized)
  );
}

/** Mirrors MaintenanceAlertCalculator.computeAlerts/computeOne -- skips
 * inactive/dismissed schedules, computes days/usage-until-due from the
 * already-server-computed next_due_date/next_due_usage, and classifies as
 * "overdue" (server-authoritative is_overdue) or "due_soon" (within either
 * threshold but not yet overdue). Returns nothing for a schedule that's
 * neither. [currentUsage] is null for equipment assets (no usage-tracking
 * field on web today, matching a pre-existing backend gap -- see this
 * feature's plan) or when a vehicle simply has no current_mileage set yet.
 */
export function computeAlerts(schedules: MaintenanceSchedule[], currentUsage: number | null): ScheduleAlert[] {
  const today = new Date().toISOString().slice(0, 10);
  const alerts: ScheduleAlert[] = [];

  for (const schedule of schedules) {
    if (!schedule.active || schedule.dismissed_at != null) continue;

    const daysUntilDue = schedule.next_due_date != null ? daysBetween(today, schedule.next_due_date) : null;
    const usageUntilDue =
      schedule.next_due_usage != null && currentUsage != null ? schedule.next_due_usage - currentUsage : null;

    const isDueSoon =
      (daysUntilDue != null && daysUntilDue >= 0 && daysUntilDue <= DUE_SOON_DAYS) ||
      (usageUntilDue != null && usageUntilDue >= 0 && usageUntilDue <= DUE_SOON_USAGE);

    if (!schedule.is_overdue && !isDueSoon) continue;

    alerts.push({
      schedule,
      severity: schedule.is_overdue ? "overdue" : "due_soon",
      daysUntilDue,
      usageUntilDue,
    });
  }

  return alerts;
}

function daysBetween(fromIso: string, toIso: string): number {
  const msPerDay = 24 * 60 * 60 * 1000;
  return Math.round((Date.parse(toIso) - Date.parse(fromIso)) / msPerDay);
}
