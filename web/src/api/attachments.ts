import { apiFetch, apiFetchBlob, apiUpload } from "./client";
import type { Attachment } from "./types";

export function listAttachmentsForRecord(recordId: string): Promise<Attachment[]> {
  return apiFetch(`/attachments?record_id=${recordId}`);
}

export function uploadAttachment(recordId: string, file: File): Promise<Attachment> {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload(`/attachments?record_id=${recordId}`, formData);
}

export function deleteAttachment(id: string): Promise<void> {
  return apiFetch(`/attachments/${id}`, { method: "DELETE" });
}

export function fetchAttachmentBlob(id: string): Promise<Blob> {
  return apiFetchBlob(`/attachments/${id}/blob`);
}
