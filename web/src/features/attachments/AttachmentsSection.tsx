import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  deleteAttachment,
  fetchAttachmentBlob,
  listAttachmentsForRecord,
  uploadAttachment,
} from "../../api/attachments";

export function AttachmentsSection({ recordId }: { recordId: string }) {
  const queryClient = useQueryClient();
  const { data: attachments, isLoading } = useQuery({
    queryKey: ["attachments", recordId],
    queryFn: () => listAttachmentsForRecord(recordId),
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadAttachment(recordId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["attachments", recordId] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAttachment(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["attachments", recordId] }),
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
