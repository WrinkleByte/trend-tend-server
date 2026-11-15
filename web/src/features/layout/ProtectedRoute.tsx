// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "../../auth/authStore";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const status = useAuthStore((s) => s.status);
  // main.tsx restores the session from the refresh cookie before the first
  // render, so this is normally settled already; render nothing rather than
  // bouncing a signed-in user to the login page if it isn't.
  if (status === "restoring") return null;
  if (!accessToken) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
