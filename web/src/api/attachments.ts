import { apiFetch, apiFetchBlob, apiUpload } from "./client";
import { getAsset } from "./assets";
import type { Asset, Attachment } from "./types";

// Matches the four join tables on the backend (RecordAttachment /
// FuelLogAttachment / TripLogAttachment / AssetAttachment) — "record" here
// means MaintenanceRecord, kept short since it's the query-param prefix
// too. "asset" maps to `linked_asset_id`, distinct from the `asset_id`
// query param uploadAssetPhoto below uses -- that one sets the 1:1
// Asset.photo_attachment_id column, this one is for extra documents (e.g.
// a Valuable's PDF service manual) via the many-to-many join table.
export type AttachmentEntityType = "record" | "fuel_log" | "trip_log" | "asset";

function entityQueryParam(entityType: AttachmentEntityType): string {
  if (entityType === "record") return "record_id";
  if (entityType === "asset") return "linked_asset_id";
  return `${entityType}_id`;
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

/** Uploads every file picked before the parent entity existed yet (see
 * PendingAttachmentPicker) -- called from a create-mutation's onSuccess,
 * once the entity has a real id to attach to. Mirrors the mobile apps'
 * "pick photos, Save uploads them" flow. */
export function uploadPendingAttachments(
  entityType: AttachmentEntityType,
  entityId: string,
  files: File[],
): Promise<Attachment[]> {
  return Promise.all(files.map((file) => uploadAttachment(entityType, entityId, file)));
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
