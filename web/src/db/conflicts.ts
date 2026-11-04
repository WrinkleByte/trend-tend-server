// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { db } from "./db";
import type { PendingConflict } from "./schema";

/**
 * "Approve all" resolves every row here using its currently-shown per-item
 * choice (keep mine / keep theirs) and re-queues an outbox entry or accepts
 * server data accordingly. "Defer" is simply not calling resolve() — a
 * no-op that leaves this table and the outbox untouched, so nothing is lost
 * by ignoring the Conflict Review screen (see docs/architecture.md Section 3).
 */
export async function listPendingConflicts(): Promise<PendingConflict[]> {
  return db.pendingConflicts.orderBy("detectedAt").toArray();
}

export async function recordConflict(conflict: PendingConflict): Promise<void> {
  await db.pendingConflicts.put(conflict);
}

export async function resolveConflict(id: string): Promise<void> {
  await db.pendingConflicts.delete(id);
}
