// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Registers a Background Sync API tag on Chromium/Android where supported.
 * iOS Safari has no Background Sync API at all — see docs/pwa-offline.md —
 * so the fallback there is triggering runSync() on foreground/visibility
 * changes and navigator.onLine transitions, implemented in Phase 4.
 */
export function registerBackgroundSyncFallbacks(onSyncTrigger: () => void): () => void {
  const handleVisibility = () => {
    if (document.visibilityState === "visible") onSyncTrigger();
  };
  const handleOnline = () => onSyncTrigger();

  document.addEventListener("visibilitychange", handleVisibility);
  window.addEventListener("online", handleOnline);

  return () => {
    document.removeEventListener("visibilitychange", handleVisibility);
    window.removeEventListener("online", handleOnline);
  };
}
