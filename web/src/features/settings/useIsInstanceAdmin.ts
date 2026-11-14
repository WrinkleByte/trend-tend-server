// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useQuery } from "@tanstack/react-query";
import { getInstanceSettings } from "../../api/instanceSettings";

/** Whether the signed-in user administers this server. There is no "who am
 * I" endpoint that says so; the instance-settings endpoint answers 403 for
 * everyone else, and the settings sections already share this query, so it
 * costs no extra request. undefined while the answer is still loading. */
export function useIsInstanceAdmin(): boolean | undefined {
  const { isSuccess, isError } = useQuery({
    queryKey: ["instance-settings"],
    queryFn: getInstanceSettings,
    retry: false,
  });
  if (isSuccess) return true;
  if (isError) return false;
  return undefined;
}
