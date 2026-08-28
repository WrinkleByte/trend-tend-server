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
//
// Mirrors tendfida-mobile's shared/.../domain/MaintenanceCategories.kt --
// the union of its VEHICLE_CATEGORIES and PROPERTY_CATEGORIES (web has no
// per-asset-type split like mobile does, so one flat list covers both).
// Previously a narrower, web-only 7-item list with a divergent "other"
// custom-sentinel; unified onto mobile's vocabulary and its "custom"
// sentinel so a household syncing both platforms sees one consistent set
// instead of the same real-world category round-tripping as two different
// stored strings depending which platform wrote it.
export const CUSTOM_CATEGORY_VALUE = "custom";
export const RECORD_CATEGORIES = [
  "oil_change", "tires", "alignment", "tpms_sensors", "brakes", "filters", "air_filter", "fluids",
  "transmission_fluid", "coolant", "differential_front", "differential_rear",
  "battery", "inspection", "electrical", "engine", "general_service", "note",
  "lawn_mowing", "fertilizing_n", "fertilizing_s", "fertilizing_e", "fertilizing_w",
  "water_filter_change", "water_softener_salt", "gutter_cleaning", "pest_control",
  "hvac_filter_change", "smoke_co_detector", CUSTOM_CATEGORY_VALUE,
];

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

/** Every category key a record is tagged with: its primary `category` plus
 * whatever's in the additive, comma-joined `additional_categories` field
 * (Vikunja: multi-category tagging). Mirrors shared Kotlin's `allCategories`
 * helper (tendfida-mobile's `domain/MaintenanceCategories.kt`) -- keep the
 * two in sync if this logic changes. */
export function allCategories(record: MaintenanceRecord): string[] {
  const extra = record.additional_categories?.split(",").map((c) => c.trim()).filter(Boolean) ?? [];
  return [record.category, ...extra];
}

/** Mirrors getActiveSchedulesForCategorySync's case-insensitive name match
 * (tendfida-mobile) -- used both when marking an alert performed (does
 * this existing record match this schedule?) and when creating a new
 * record (does it match any active schedule, so we can offer to clear
 * one?). Checks `custom_category` too, for a record filed under the
 * "custom" sentinel, and every tag in `additional_categories`, not just
 * the primary category -- so a record tagged with both "oil_change" and
 * "tires" matches an active schedule for either. */
export function recordMatchesSchedule(record: MaintenanceRecord, scheduleName: string): boolean {
  const normalized = normalizeForMatch(scheduleName);
  return (
    allCategories(record).some((c) => normalizeForMatch(c) === normalized) ||
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
