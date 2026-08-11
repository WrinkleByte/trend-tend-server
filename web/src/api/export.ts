import { getAttachment, fetchAttachmentBlob, listAttachmentsForRecord } from "./attachments";
import { listAssets } from "./assets";
import { listFuelLogs } from "./fuelLogs";
import { listMaintenanceRecords } from "./maintenanceRecords";
import { listMaintenanceSchedules } from "./maintenanceSchedules";
import type { Asset, Attachment, FuelLog, MaintenanceRecord, MaintenanceSchedule } from "./types";

// Generalized discriminator matching mobile's AttachmentExportRow shape
// (entity_type/entity_id) rather than a record_id/asset_id split — keeps
// the two platforms' export/restore formats interchangeable. Web only ever
// produces "maintenance_record" or "asset" today (no fuel_log/trip_log
// attachment support on web yet), but a restore reading either platform's
// backup only needs to understand this one pair.
export interface AttachmentExportEntry extends Attachment {
  entity_type: 'maintenance_record' | 'asset';
  entity_id: string;
}

export interface ExportBundle {
  exported_at: string;
  assets: Asset[];
  fuel_logs: FuelLog[];
  maintenance_records: MaintenanceRecord[];
  maintenance_schedules: MaintenanceSchedule[];
  attachments: AttachmentExportEntry[];
}

export async function gatherExportData(): Promise<ExportBundle> {
  const [assets, fuelLogs, maintenanceRecords, maintenanceSchedules] = await Promise.all([
    listAssets(),
    listFuelLogs(),
    listMaintenanceRecords(),
    listMaintenanceSchedules(),
  ]);

  // Attachments are only listable per record — there's no household-wide
  // endpoint — so we fan out one request per maintenance record.
  const attachmentLists = await Promise.all(
    maintenanceRecords.map((record) =>
      listAttachmentsForRecord(record.id).then((atts) =>
        atts.map((attachment): AttachmentExportEntry => ({ ...attachment, entity_type: 'maintenance_record', entity_id: record.id })),
      ),
    ),
  );

  // Asset profile photos are a direct FK on the asset row, not a listable
  // link — one GET /attachments/{id} per asset that actually has one.
  const assetPhotoEntries = await Promise.all(
    assets
      .filter((asset): asset is Asset & { photo_attachment_id: string } => asset.photo_attachment_id !== null)
      .map((asset) =>
        getAttachment(asset.photo_attachment_id).then(
          (attachment): AttachmentExportEntry => ({ ...attachment, entity_type: 'asset', entity_id: asset.id }),
        ),
      ),
  );

  return {
    exported_at: new Date().toISOString(),
    assets,
    fuel_logs: fuelLogs,
    maintenance_records: maintenanceRecords,
    maintenance_schedules: maintenanceSchedules,
    attachments: [...attachmentLists.flat(), ...assetPhotoEntries],
  };
}

export async function fetchAllAttachmentBlobs(
  attachments: AttachmentExportEntry[],
  onProgress?: (done: number, total: number) => void,
): Promise<{ attachment: AttachmentExportEntry; blob: Blob }[]> {
  const results: { attachment: AttachmentExportEntry; blob: Blob }[] = [];
  for (const attachment of attachments) {
    const blob = await fetchAttachmentBlob(attachment.id);
    results.push({ attachment, blob });
    onProgress?.(results.length, attachments.length);
  }
  return results;
}
