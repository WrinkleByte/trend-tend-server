import { apiFetch, apiFetchBlob, apiUpload } from "./client";
import { getAsset } from "./assets";
import type { Asset, Attachment } from "./types";

// Matches the three join tables on the backend (RecordAttachment /
// FuelLogAttachment / TripLogAttachment) — "record" here means
// MaintenanceRecord, kept short since it's the query-param prefix too.
export type AttachmentEntityType = "record" | "fuel_log" | "trip_log";

function entityQueryParam(entityType: AttachmentEntityType): string {
  return entityType === "record" ? "record_id" : `${entityType}_id`;
}

export function listAttachments(entityType: AttachmentEntityType, entityId: string): Promise<Attachment[]> {
  return apiFetch(`/attachments?${entityQueryParam(entityType)}=${entityId}`);
}

export function uploadAttachment(
  entityType: AttachmentEntityType,
  entityId: string,
  file: File,
): Promise<Attachment> {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload(`/attachments?${entityQueryParam(entityType)}=${entityId}`, formData);
}

export function getAttachment(id: string): Promise<Attachment> {
  return apiFetch(`/attachments/${id}`);
}

export function deleteAttachment(id: string): Promise<void> {
  return apiFetch(`/attachments/${id}`, { method: "DELETE" });
}

export function fetchAttachmentBlob(id: string): Promise<Blob> {
  return apiFetchBlob(`/attachments/${id}/blob`);
}

// Asset profile photo — a direct 1:1 FK on the asset row (Asset.photo_
// attachment_id), not a join-table link like record attachments, so
// setting it returns the updated Asset (whose new photo_attachment_id the
// caller needs) rather than just the Attachment.
export function uploadAssetPhoto(assetId: string, file: File): Promise<Asset> {
  const formData = new FormData();
  formData.append("file", file);
  // upload_attachment's response_model is AttachmentResponse (the new
  // attachment), not the Asset it just got linked to — refetch the asset so
  // the caller sees its updated photo_attachment_id.
  return apiUpload(`/attachments?asset_id=${assetId}`, formData).then(() => getAsset(assetId));
}

export function removeAssetPhoto(assetId: string): Promise<void> {
  return apiFetch(`/assets/${assetId}/photo`, { method: "DELETE" });
}
