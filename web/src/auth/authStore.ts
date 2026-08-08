import { create } from "zustand";
import { persist } from "zustand/middleware";

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
    { name: "tendfida-auth" },
  ),
);

export function isAuthenticated(): boolean {
  return useAuthStore.getState().accessToken !== null;
}
