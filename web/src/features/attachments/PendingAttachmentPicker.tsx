// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useRef } from "react";

/** Lets the user pick photos before the parent entity (a maintenance
 * record, fuel log, trip) exists yet -- held in the parent form's own
 * state and uploaded via uploadPendingAttachments once the create
 * mutation actually returns a real id. Mirrors the mobile apps'
 * "pick photos, Save uploads them" flow (PendingAttachmentStrip). Not
 * receipt-specific -- these are general photo attachments (odometer
 * shots, damage photos, etc.), not just receipts, hence "Add Picture"
 * rather than "Add Receipt". */
export function PendingAttachmentPicker({
  files,
  onFilesChange,
}: {
  files: File[];
  onFilesChange: (files: File[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="pending-attachment-picker">
      <button type="button" className="add-picture-button" onClick={() => inputRef.current?.click()}>
        Add Picture{files.length > 0 ? ` (${files.length})` : ""}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/*,application/pdf"
        multiple
        className="visually-hidden-file-input"
        onChange={(e) => {
          const picked = Array.from(e.target.files ?? []);
          if (picked.length > 0) onFilesChange([...files, ...picked]);
          e.target.value = "";
        }}
      />
      {files.length > 0 && (
        <ul className="pending-attachment-list">
          {files.map((file, index) => (
            <li key={`${file.name}-${index}`}>
              <span>{file.name}</span>
              <button
                type="button"
                onClick={() => onFilesChange(files.filter((_, i) => i !== index))}
                aria-label={`Remove ${file.name}`}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
