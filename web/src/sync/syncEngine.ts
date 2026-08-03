/**
 * Phase 4 component (see docs/architecture.md Sections 3 & 7): orchestrates
 * pull -> apply -> collect-outbox -> push -> resolve against the same
 * /sync/pull and /sync/push contract the mobile apps use. Left as a stub in
 * this scaffold — sequenced after the sync protocol is battle-tested
 * against real mobile clients (Phase 2/3) so the web implementation targets
 * a stable, debugged contract rather than co-evolving both at once.
 */
export async function runSync(): Promise<void> {
  throw new Error("Not implemented — see docs/architecture.md Section 3 and Phase 4 of the roadmap");
}
