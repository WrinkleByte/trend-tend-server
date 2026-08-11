import { useEffect, useState } from "react";

// Pure local UI preference — mirrors mobile's AppSettingsKeys.assetPhotosEnabled
// (iOS @AppStorage / Android DataStore): never synced, just visibility of the
// profile-photo button, not the underlying photo data. No per-user settings
// API exists on the backend to put this on instead (see InstanceSettingsSection,
// which is instance-admin config, not a per-user preference).
const STORAGE_KEY = "assetPhotosEnabled";

function readStoredValue(): boolean {
  if (typeof localStorage === "undefined") return true;
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw === null ? true : raw === "true";
}

export function useAssetPhotosEnabled(): [boolean, (value: boolean) => void] {
  const [enabled, setEnabled] = useState(readStoredValue);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(enabled));
  }, [enabled]);

  return [enabled, setEnabled];
}
