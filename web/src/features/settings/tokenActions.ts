// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import type { QueryClient } from "@tanstack/react-query";

/**
 * One pairing code (an API key), and what the person looking at it is allowed to do.
 *
 * Both halves of this live in one place because a pairing code is listed on two pages --
 * Settings › API Tokens shows your own keys, the Household page shows a member's -- and the two
 * pages used to disagree about what a revoked key even is (Vikunja #196). The Household page
 * filtered revoked keys out of its list, so the Delete button that only a revoked key has was
 * unreachable there; the Settings page showed the row and had the button, but for a member's key
 * the delete call was the own-keys-only endpoint and answered 404 with nothing on screen.
 */
export interface TokenLike {
  revoked_at: string | null;
}

export interface TokenActions {
  readonly canRevoke: boolean;
  readonly canDelete: boolean;
}

/**
 * Revoking is the security action and always available for a live key; deleting is the
 * housekeeping one and only exists once the key is revoked -- the backend enforces that order
 * (`api_tokens.py`'s `delete_api_token`, and `households.py` for a member's key), because wiping
 * a live key would destroy the trail of a credential that was in use and skip the moment where
 * you notice you revoked the wrong device.
 */
export function tokenActions(token: TokenLike, canManage: boolean): TokenActions {
  const revoked = token.revoked_at !== null;
  return {
    canRevoke: canManage && !revoked,
    canDelete: canManage && revoked,
  };
}

/**
 * Every key the server returned, revoked ones included.
 *
 * There is deliberately no filter here. A revoked key is the one row that still needs an action
 * (Delete), so hiding it is what made the button look missing; it also hides the case where
 * someone revoked the wrong device and wants to see that they did.
 */
export function deviceRows<T extends TokenLike>(tokens: T[] | undefined): T[] {
  return tokens ?? [];
}

export type DeviceRowState = "revoked" | "used" | "never";

/** What the row's status column says about a key. A revoked key reads as revoked even if it was
 * used: "last synced" on a dead key invites the reading that it is still live. */
export function deviceRowState(token: TokenLike & { last_used_at: string | null }): DeviceRowState {
  if (token.revoked_at !== null) return "revoked";
  return token.last_used_at ? "used" : "never";
}

/**
 * A pairing code appears in two queries (`["api-tokens"]` for your own keys,
 * `["member-api-tokens", <user>]` for a member's). Revoking or deleting through one page leaves
 * the other page offering the action it just made stale -- a Revoke button on a key that is
 * already revoked, which is exactly the "revoking doesn't consistently show the delete button"
 * shape. Invalidate both, from both pages.
 */
export function invalidateTokenLists(queryClient: QueryClient): void {
  queryClient.invalidateQueries({ queryKey: ["api-tokens"] });
  queryClient.invalidateQueries({ queryKey: ["member-api-tokens"] });
}
