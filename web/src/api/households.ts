// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { apiFetch } from "./client";
import type {
  ApiTokenCreated,
  ApiTokenSummary,
  CreatedHouseholdInvite,
  Household,
  HouseholdInvite,
  HouseholdMember,
  InvitePreview,
  TokenResponse,
} from "./types";

export function getCurrentHousehold(): Promise<Household> {
  return apiFetch("/households/me");
}

export function listMembers(): Promise<HouseholdMember[]> {
  return apiFetch("/households/members");
}

/** Adds a family member who won't have a web login of their own (owner only).
 * With an email, they can later use "Forgot password" to get one. */
export function addAppOnlyMember(
  displayName: string,
  email: string | null,
  role: "owner" | "member" = "member",
): Promise<HouseholdMember> {
  return apiFetch("/households/members", {
    method: "POST",
    body: JSON.stringify({ display_name: displayName, email: email || null, role }),
  });
}

/** A pairing key for another member (owner only): a device paired with it syncs as them. */
export function createMemberApiToken(userId: string, name: string): Promise<ApiTokenCreated> {
  return apiFetch(`/households/members/${userId}/api-tokens`, { method: "POST", body: JSON.stringify({ name }) });
}

export function listMemberApiTokens(userId: string): Promise<ApiTokenSummary[]> {
  return apiFetch(`/households/members/${userId}/api-tokens`);
}

export function revokeMemberApiToken(userId: string, tokenId: string): Promise<void> {
  return apiFetch(`/households/members/${userId}/api-tokens/${tokenId}`, { method: "DELETE" });
}

/** Owner only, revoked keys only: remove a member's pairing code for good (Vikunja #196). This is
 * the household route -- `/api-tokens/{id}/permanently` is own-keys-only and answers 404 for a
 * member's key, which is why Delete could never clear a member's row. */
export function deleteMemberApiToken(userId: string, tokenId: string): Promise<void> {
  return apiFetch(`/households/members/${userId}/api-tokens/${tokenId}/permanently`, { method: "DELETE" });
}

export function removeMember(userId: string): Promise<void> {
  return apiFetch(`/households/members/${userId}`, { method: "DELETE" });
}

export function deleteHousehold(): Promise<void> {
  return apiFetch("/households/me", { method: "DELETE" });
}

export function wipeHouseholdData(): Promise<void> {
  return apiFetch("/households/me/wipe-data", { method: "POST" });
}

export function listInvites(): Promise<HouseholdInvite[]> {
  return apiFetch("/households/invites");
}

export function createInvite(
  invitedEmail: string,
  role: "owner" | "member" = "member",
): Promise<CreatedHouseholdInvite> {
  return apiFetch("/households/invites", {
    method: "POST",
    body: JSON.stringify({ invited_email: invitedEmail, role }),
  });
}

export function revokeInvite(inviteId: string): Promise<void> {
  return apiFetch(`/households/invites/${inviteId}`, { method: "DELETE" });
}

export function previewInvite(token: string): Promise<InvitePreview> {
  return apiFetch(`/households/invites/by-token/${encodeURIComponent(token)}`);
}

export function acceptInvite(token: string): Promise<TokenResponse> {
  return apiFetch("/households/invites/accept", { method: "POST", body: JSON.stringify({ token }) });
}
