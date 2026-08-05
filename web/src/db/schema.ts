import Dexie, { type EntityTable } from "dexie";

/**
 * Local IndexedDB schema (via Dexie) mirroring the backend entities 1:1 —
 * the browser-world equivalent of the mobile apps' SQLDelight database. See
 * ../../../docs/architecture.md Section 1 for the canonical field lists and
 * ../../../docs/pwa-offline.md for why Dexie (not raw IndexedDB or PouchDB).
 *
 * Every syncable table carries the same sync envelope fields used by the
 * backend and the mobile shared module: id, householdId, createdAt,
 * updatedAt, updatedByDeviceId, deletedAt, version.
 */

export interface SyncEnvelope {
  id: string;
  householdId: string;
  createdAt: string;
  updatedAt: string;
  updatedByDeviceId: string | null;
  deletedAt: string | null;
  version: number;
}

export interface Asset extends SyncEnvelope {
  assetType: "vehicle" | "equipment" | "property" | "home_system";
  name: string;
  notes: string | null;
  photoAttachmentId: string | null;
  status: "active" | "archived" | "disposed";
  purchaseDate: string | null;
  purchaseCost: number | null;
}

export interface MaintenanceRecord extends SyncEnvelope {
  assetId: string;
  performedAt: string;
  performedBy: string | null;
  category: string;
  customCategory: string | null;
  description: string | null;
  cost: number | null;
  currency: string;
  odometerReading: number | null;
  scheduleId: string | null;
}

export interface MaintenanceSchedule extends SyncEnvelope {
  assetId: string;
  name: string;
  intervalType: "time" | "usage" | "both";
  intervalDays: number | null;
  intervalUsageAmount: number | null;
  usageField: string | null;
  anchorDate: string | null;
  anchorUsageValue: number | null;
  active: boolean;
}

export interface Attachment extends SyncEnvelope {
  originalFilename: string;
  contentType: string;
  sizeBytes: number;
  sha256: string;
  thumbnailStorageKey: string | null;
  capturedAt: string | null;
}

/** Mirrors the mobile shared module's outboxEntry table (Tendfida.sq) —
 * every local write also upserts a row here for SyncEngine to drain. */
export interface OutboxEntry {
  id: string;
  entityType: string;
  entityId: string;
  baseVersion: number;
  queuedAt: string;
}

/** Populated on a push "conflict" result in manual-resolution mode; a no-op
 * "defer" leaves this table untouched (see docs/architecture.md Section 3). */
export interface PendingConflict {
  id: string;
  entityType: string;
  entityId: string;
  localData: unknown;
  serverData: unknown;
  detectedAt: string;
}

export class TendfidaDb extends Dexie {
  assets!: EntityTable<Asset, "id">;
  maintenanceRecords!: EntityTable<MaintenanceRecord, "id">;
  maintenanceSchedules!: EntityTable<MaintenanceSchedule, "id">;
  attachments!: EntityTable<Attachment, "id">;
  outbox!: EntityTable<OutboxEntry, "id">;
  pendingConflicts!: EntityTable<PendingConflict, "id">;

  constructor() {
    super("tendfida");
    this.version(1).stores({
      assets: "id, householdId, assetType, deletedAt",
      maintenanceRecords: "id, householdId, assetId, performedAt, deletedAt",
      maintenanceSchedules: "id, householdId, assetId, deletedAt",
      attachments: "id, householdId, sha256, deletedAt",
      outbox: "id, entityType, queuedAt",
      pendingConflicts: "id, entityType, detectedAt",
    });
  }
}
