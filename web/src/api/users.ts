// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { apiFetch } from "./client";
import type { Me } from "./types";

/** Change your own display name; everyone in the household sees the new one. */
export function updateMyDisplayName(displayName: string): Promise<Me> {
  return apiFetch("/users/me", { method: "PATCH", body: JSON.stringify({ display_name: displayName }) });
}
