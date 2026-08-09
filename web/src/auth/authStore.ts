import { create } from "zustand";
import { persist } from "zustand/middleware";

const LEGACY_AUTH_KEY = "tendfida-auth";
const AUTH_KEY = "wrinklebyte-auth";

// One-time carry-forward of the persisted auth state from the pre-rename
// localStorage key, so an existing installed PWA doesn't get silently
// logged out by the rebrand. Must run before `persist()` below does its
// own (synchronous) hydration read, so this executes as a top-level
// module side effect rather than inside the store itself.
if (typeof localStorage !== "undefined" && !localStorage.getItem(AUTH_KEY)) {
  const legacy = localStorage.getItem(LEGACY_AUTH_KEY);
  if (legacy) {
    localStorage.setItem(AUTH_KEY, legacy);
    localStorage.removeItem(LEGACY_AUTH_KEY);
  }
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  setTokens: (accessToken: string, refreshToken: string) => void;
  clear: () => void;
}

/** Persisted to localStorage so a page refresh doesn't log the user out.
 * See ../api/client.ts for how these tokens get attached to requests and
 * refreshed on expiry. */
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      setTokens: (accessToken, refreshToken) => set({ accessToken, refreshToken }),
      clear: () => set({ accessToken: null, refreshToken: null }),
    }),
    { name: AUTH_KEY },
  ),
);

export function isAuthenticated(): boolean {
  return useAuthStore.getState().accessToken !== null;
}
