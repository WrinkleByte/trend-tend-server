// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { create } from "zustand";

/**
 * The signed-in session, in memory only (Vikunja #93).
 *
 * The short-lived access token (15 minutes) lives here and nowhere else.
 * The refresh token is an HttpOnly cookie the server sets, which no script
 * on this page can read, so a cross-site-scripting bug can no longer walk
 * off with a 30-day session. A page reload starts at "restoring" and
 * ../api/client.ts's restoreSession() turns the cookie back into an access
 * token. Both tokens used to sit in localStorage; client.ts moves an old
 * session over once, then deletes it (see takeLegacyRefreshToken below).
 */
export type SessionStatus = "restoring" | "signed-in" | "signed-out";

interface AuthState {
  accessToken: string | null;
  status: SessionStatus;
  setAccessToken: (accessToken: string) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>()((set) => ({
  accessToken: null,
  status: "restoring",
  setAccessToken: (accessToken) => set({ accessToken, status: "signed-in" }),
  clear: () => set({ accessToken: null, status: "signed-out" }),
}));

export function isAuthenticated(): boolean {
  return useAuthStore.getState().accessToken !== null;
}

// Where earlier versions persisted both tokens (zustand's persist middleware,
// before and after the WrinkleByte rename).
const LEGACY_KEYS = ["wrinklebyte-auth", "tendfida-auth"];

/** The refresh token an earlier version left in localStorage, if any, so
 * client.ts can trade it for the cookie once. */
export function readLegacyRefreshToken(): string | null {
  try {
    for (const key of LEGACY_KEYS) {
      const raw = localStorage.getItem(key);
      if (!raw) continue;
      const token = (JSON.parse(raw) as { state?: { refreshToken?: unknown } })?.state?.refreshToken;
      if (typeof token === "string" && token) return token;
    }
  } catch {
    // Private windows and blocked site data throw on access; unparseable
    // leftovers are simply ignored.
  }
  return null;
}

/** Remove every localStorage copy of the old tokens. */
export function forgetLegacyTokens(): void {
  try {
    for (const key of LEGACY_KEYS) localStorage.removeItem(key);
  } catch {
    // Nothing to remove if storage is unavailable.
  }
}
