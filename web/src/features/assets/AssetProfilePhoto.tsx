// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchAttachmentBlob, removeAssetPhoto, uploadAssetPhoto } from "../../api/attachments";
import { useAssetPhotosEnabled } from "../settings/assetPhotosSetting";
import type { Asset } from "../../api/types";

// The web counterpart to mobile's circular profile-photo button at the top
// of the asset detail screen (AssetDetailView.swift/AssetDetailScreen.kt) —
// same capability (set/replace/remove, toggle-able), backed by the asset's
// direct photo_attachment_id FK rather than mobile's local-only file.
export function AssetProfilePhoto({ asset }: { asset: Asset }) {
  const queryClient = useQueryClient();
  const [assetPhotosEnabled] = useAssetPhotosEnabled();
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!asset.photo_attachment_id) {
      setObjectUrl(null);
      return;
    }
    let cancelled = false;
    let createdUrl: string | null = null;
    // Blob endpoint requires the Authorization header, so a plain <img src>
    // can't hit it directly — same pattern AttachmentsSection.handleView uses.
    fetchAttachmentBlob(asset.photo_attachment_id).then((blob) => {
      if (cancelled) return;
      createdUrl = URL.createObjectURL(blob);
      setObjectUrl(createdUrl);
    });
    return () => {
      cancelled = true;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [asset.photo_attachment_id]);

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadAssetPhoto(asset.id, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets", asset.id] }),
  });

  const removeMutation = useMutation({
    mutationFn: () => removeAssetPhoto(asset.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets", asset.id] }),
  });

  if (!assetPhotosEnabled) return null;

  return (
    <div className="asset-profile-photo">
      <div className="asset-photo-circle">
        {objectUrl ? (
          <img src={objectUrl} alt={`${asset.name} profile`} />
        ) : (
          <span aria-hidden="true">📷</span>
        )}
      </div>
      <div className="asset-photo-actions">
        <label className="secondary">
          <input
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadMutation.mutate(file);
              e.target.value = "";
            }}
          />
          {asset.photo_attachment_id ? "Change photo" : "Add photo"}
        </label>
        {asset.photo_attachment_id && (
          <button
            type="button"
            className="danger"
            onClick={() => removeMutation.mutate()}
            disabled={removeMutation.isPending}
          >
            Remove
          </button>
        )}
      </div>
    </div>
  );
}
