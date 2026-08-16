import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteAttachment, fetchAttachmentBlob, listAttachments, uploadAttachment } from "../../api/attachments";
import type { AttachmentEntityType } from "../../api/attachments";

export function AttachmentsSection({
  entityType,
  entityId,
}: {
  entityType: AttachmentEntityType;
  entityId: string;
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

  async function handleView(id: string) {
    // Blob endpoint requires the Authorization header, so a plain <img>/<a>
    // src can't hit it directly — fetch with auth, then open an object URL.
    const blob = await fetchAttachmentBlob(id);
    window.open(URL.createObjectURL(blob), "_blank");
  }

  return (
    <div className="attachments-section">
      <input
        type="file"
        accept="image/*,application/pdf"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) uploadMutation.mutate(file);
          e.target.value = "";
        }}
      />
      {isLoading && <p>Loading receipts…</p>}
      <ul className="attachment-list">
        {attachments?.map((attachment) => (
          <li key={attachment.id}>
            <button type="button" onClick={() => handleView(attachment.id)}>
              {attachment.original_filename}
            </button>
            <button type="button" className="danger" onClick={() => deleteMutation.mutate(attachment.id)}>
              Remove
            </button>
          </li>
        ))}
      </ul>
      {attachments?.length === 0 && <p>No receipts attached.</p>}
    </div>
  );
}
