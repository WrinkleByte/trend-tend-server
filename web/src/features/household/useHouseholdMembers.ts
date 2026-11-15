// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useQuery } from "@tanstack/react-query";
import { getCurrentHousehold, listMembers } from "../../api/households";
import type { HouseholdMember } from "../../api/types";

/**
 * The household's members, plus a user_id → display name lookup for the
 * places that only store an id: an asset's owner, and the `updated_by_user_id`
 * attribution the backend now stamps on every synced row.
 *
 * Shares the ["members"] query key with HouseholdPage so the member list is
 * fetched once and reused rather than per consumer.
 */
export function useHouseholdMembers() {
  const { data: members, isLoading } = useQuery({ queryKey: ["members"], queryFn: listMembers });

  // Same ["household"] key as HouseholdPage, so this is one shared fetch.
  const { data: household } = useQuery({ queryKey: ["household"], queryFn: getCurrentHousehold });
  const myUserId = household?.my_user_id;

  const byId = new Map<string, HouseholdMember>((members ?? []).map((m) => [m.user_id, m]));

  /** For pickers: you first, then everyone else in join order. */
  const pickerMembers = (members ?? []).slice().sort((a, b) => Number(b.user_id === myUserId) - Number(a.user_id === myUserId));

  /**
   * A member's name as a picker shows it (Vikunja #164): "Me (Name)" for you,
   * and the email (or "app only") after a name two members share, so two
   * people both called "Alex" can be told apart.
   */
  function pickerLabel(member: HouseholdMember): string {
    const name = member.user_id === myUserId ? `Me (${member.display_name})` : member.display_name;
    const shared = (members ?? []).filter((m) => m.display_name === member.display_name).length > 1;
    if (!shared) return name;
    return `${name} \u00b7 ${member.email || "app only"}`;
  }

  /**
   * Falls back to "Someone" rather than rendering a raw UUID: a member who has
   * since been removed from the household still shows up as the last editor of
   * rows they touched (deletion nulls the column, but removal from a household
   * does not), and an id is worse than useless in the UI.
   */
  function nameFor(userId: string | null | undefined): string | null {
    if (!userId) return null;
    return byId.get(userId)?.display_name ?? "Someone";
  }

  return { members, isLoading, byId, nameFor, myUserId, pickerMembers, pickerLabel };
}
