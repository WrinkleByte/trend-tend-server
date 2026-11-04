// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { db } from "./db";
import type { OutboxEntry } from "./schema";

/**
 * Every local write to a syncable entity should call queueOutboxEntry so
 * syncEngine has something to push. Mirrors the mobile shared module's
 * Outbox.kt — see docs/architecture.md Section 3.
 */
export async function queueOutboxEntry(entry: OutboxEntry): Promise<void> {
  await db.outbox.put(entry);
}

export async function drainOutbox(): Promise<OutboxEntry[]> {
  return db.outbox.orderBy("queuedAt").toArray();
}

export async function clearOutboxEntry(id: string): Promise<void> {
  await db.outbox.delete(id);
}
