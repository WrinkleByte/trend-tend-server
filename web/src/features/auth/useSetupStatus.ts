// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useQuery } from "@tanstack/react-query";
import { getSetupStatus } from "../../api/auth";

/**
 * Shared accessor for GET /auth/setup-status — the one unauthenticated probe
 * every client makes on load, carrying both the first-run flag and whether
 * self-service signup is open.
 *
 * Same query key and staleTime as SetupGate deliberately: react-query then
 * serves every consumer (the gate, the login page's "Register" link, the
 * register page itself) from one cached response instead of refetching per
 * component.
 */
export function useSetupStatus() {
  return useQuery({
    queryKey: ["setup-status"],
    queryFn: getSetupStatus,
    staleTime: Infinity,
  });
}
