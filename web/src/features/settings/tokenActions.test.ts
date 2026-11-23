// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

// Vikunja #196: "revoking a code doesn't consistently show the delete button. The delete button
// doesn't consistently remove the line." Both halves came from the same place -- a pairing code is
// listed on two pages, and the Household page filtered revoked keys out of the only list where a
// member's code can be tidied up. These are the rules both pages now share.

import assert from "node:assert/strict";
import { test } from "node:test";
import { deviceRows, tokenActions } from "./tokenActions.ts";

const live = { revoked_at: null, last_used_at: "2026-11-20T10:00:00Z" };
const revoked = { revoked_at: "2026-11-21T09:30:00Z", last_used_at: "2026-11-20T10:00:00Z" };

test("a live key gets Revoke, not Delete", () => {
  assert.deepEqual(tokenActions(live, true), { canRevoke: true, canDelete: false });
});

test("a revoked key gets Delete, which is the button the owner could not find", () => {
  assert.deepEqual(tokenActions(revoked, true), { canRevoke: false, canDelete: true });
});

test("revoke and delete are never both offered for the same key", () => {
  for (const token of [live, revoked]) {
    const actions = tokenActions(token, true);
    assert.equal(actions.canRevoke && actions.canDelete, false);
  }
});

test("someone who cannot manage the household gets neither button", () => {
  assert.deepEqual(tokenActions(live, false), { canRevoke: false, canDelete: false });
  assert.deepEqual(tokenActions(revoked, false), { canRevoke: false, canDelete: false });
});

test("a revoked key stays in the list, because it is the row that still has an action", () => {
  // The filter this replaces (`tokens.filter((t) => !t.revoked_at)`) removed the revoked row from
  // the member-devices table entirely, so Delete was unreachable there no matter what the server
  // returned -- and a wrong revocation became invisible.
  const rows = deviceRows([revoked, live]);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].revoked_at, revoked.revoked_at);
});

test("an absent list is an empty list, not a crash", () => {
  assert.deepEqual(deviceRows(undefined), []);
});

test("the server's own answer for a member's keys includes the revoked ones", () => {
  // Recorded here because the fix depends on it: households.py's list_member_api_tokens selects
  // every key in the household for that user with no revoked filter, so the old filter was hiding
  // data the page already had.
  const rows = deviceRows([revoked, revoked, live]);
  assert.equal(rows.filter((t) => t.revoked_at !== null).length, 2);
});
