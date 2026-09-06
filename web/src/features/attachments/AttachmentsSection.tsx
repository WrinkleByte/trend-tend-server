import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteAttachment, fetchAttachmentBlob, listAttachments, uploadAttachment } from "../../api/attachments";
import type { AttachmentEntityType } from "../../api/attachments";
import type { Attachment } from "../../api/types";

export function AttachmentsSection({
  entityType,
  entityId,
  addButtonLabel = "Add Picture",
  emptyLabel = "No photos attached.",
}: {
  entityType: AttachmentEntityType;
  entityId: string;
  addButtonLabel?: string;
  emptyLabel?: string;
}) {
  const queryClient = useQueryClient();
  const queryKey = ["attachments", entityType, entityId];
  const { data: attachments, isLoading } = useQuery({
    queryKey,
    queryFn: () => listAttachments(entityType, entityId),
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadAttachment(entityType, entityId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAttachment(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="attachments-section">
      <button type="button" className="add-picture-button" onClick={() => inputRef.current?.click()}>
        {addButtonLabel}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/*,application/pdf"
        className="visually-hidden-file-input"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) uploadMutation.mutate(file);
          e.target.value = "";
        }}
      />
      {isLoading && <p>Loading photos…</p>}
      <div className="attachment-thumbnail-strip">
        {attachments?.map((attachment) => (
          <AttachmentThumbnail
            key={attachment.id}
            attachment={attachment}
            onDelete={() => deleteMutation.mutate(attachment.id)}
          />
        ))}
      </div>
      {attachments?.length === 0 && <p>{emptyLabel}</p>}
    </div>
  );
}

function AttachmentThumbnail({ attachment, onDelete }: { attachment: Attachment; onDelete: () => void }) {
  const isImage = attachment.content_type.startsWith("image/");

  // Cache the Blob itself (safe to share/reuse across mounts), but create
  // and revoke the object URL locally per mount -- an object URL cached
  // and revoked by some *other* component instance unmounting would break
  // this one's still-visible <img>, so each instance owns its own URL
  // lifecycle even though the underlying network fetch is deduped.
  const { data: blob } = useQuery({
    queryKey: ["attachment-blob", attachment.id],
    queryFn: () => fetchAttachmentBlob(attachment.id),
    enabled: isImage,
    staleTime: Infinity, // content-addressed by sha256 server-side -- never changes once uploaded
  });
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!blob) {
      setObjectUrl(null);
      return;
    }
    const url = URL.createObjectURL(blob);
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [blob]);

  async function handleView() {
    // Already fetched for image thumbnails; a non-image (PDF) fetches on
    // click instead, since there's nothing to preview inline for it.
    const viewBlob = blob ?? (await fetchAttachmentBlob(attachment.id));
    window.open(URL.createObjectURL(viewBlob), "_blank");
  }

  return (
    <div className="attachment-thumbnail">
      <button
        type="button"
        className="attachment-thumbnail-image"
        onClick={handleView}
        aria-label={`View ${attachment.original_filename}`}
        title={attachment.original_filename}
      >
        {isImage && objectUrl ? (
          <img src={objectUrl} alt={attachment.original_filename} />
        ) : (
          <span className="attachment-thumbnail-icon" aria-hidden="true">
            {isImage ? "" : "📄"}
          </span>
        )}
      </button>
      <button
        type="button"
        className="attachment-thumbnail-remove"
        onClick={onDelete}
        aria-label={`Remove ${attachment.original_filename}`}
      >
        ×
      </button>
    </div>
  );
}
