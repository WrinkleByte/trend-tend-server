import { useQuery } from "@tanstack/react-query";
import { listMembers } from "../../api/households";
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

  const byId = new Map<string, HouseholdMember>((members ?? []).map((m) => [m.user_id, m]));

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

  return { members, isLoading, byId, nameFor };
}
