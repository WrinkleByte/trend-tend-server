// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { apiFetch } from "./client";
import type {
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
