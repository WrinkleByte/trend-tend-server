import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSetupStatus } from "../../api/auth";
import { SetupPage } from "./SetupPage";

/**
 * Wraps the whole route tree — on a freshly-deployed instance with zero
 * users, every route (login, register, join, the app itself) shows the
 * first-run "Create Admin Account" screen instead, regardless of what URL
 * was requested. Once setup_complete flips true (irreversibly, from the
 * backend's perspective — see auth.py's register()), this becomes a no-op
 * and children render normally.
 */
export function SetupGate({ children }: { children: ReactNode }) {
  const { data, isLoading } = useQuery({
    queryKey: ["setup-status"],
    queryFn: getSetupStatus,
    // Only relevant once, right after a fresh deploy — no need to keep
    // re-checking an established instance on every focus/mount.
    staleTime: Infinity,
  });

  // Deliberately render nothing (not even a spinner) while this resolves —
  // it's one fast local request, and briefly flashing the login form before
  // possibly swapping to the setup screen would be worse than a blank beat.
  if (isLoading) return null;

  if (data && !data.setup_complete) {
    return <SetupPage />;
  }

  return <>{children}</>;
}
