import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addUserMembership,
  listAllHouseholds,
  listAllUsers,
  purgeUser,
  removeUserMembership,
  type AdminUserSummary,
} from "../../api/admin";
import { ApiError } from "../../api/client";
import { StatusMessage } from "../../components/StatusMessage";

/**
 * Instance-wide user list, including orphaned accounts (Vikunja #101) —
 * AdminHouseholdsSection only ever shows a user *through* a household, so
 * a real account stuck with zero memberships (the self-service accept-
 * invite flow can leave one in exactly this state — see that card) never
 * appeared anywhere in the UI before this. "Add to household" is the fix
 * for that: it adds a membership directly, bypassing the broken invite/
 * accept round-trip entirely. "Purge" permanently deletes an account —
 * for orphans nobody's going to rescue, or accounts that should never
 * have existed.
 */
export function UserManagementSection() {
  const queryClient = useQueryClient();
  const { data: users, isError } = useQuery({ queryKey: ["admin-users"], queryFn: listAllUsers, retry: false });
  const { data: households } = useQuery({
    queryKey: ["admin-households"],
    queryFn: listAllHouseholds,
    retry: false,
  });
  const [addingFor, setAddingFor] = useState<string | null>(null);
  const [selectedHousehold, setSelectedHousehold] = useState("");
  const [selectedRole, setSelectedRole] = useState<"owner" | "member">("member");

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    queryClient.invalidateQueries({ queryKey: ["admin-households"] });
  };

  const purgeMutation = useMutation({
    mutationFn: (userId: string) => purgeUser(userId),
    onSuccess: invalidate,
  });

  const addMutation = useMutation({
    mutationFn: ({ userId, householdId, role }: { userId: string; householdId: string; role: "owner" | "member" }) =>
      addUserMembership(userId, householdId, role),
    onSuccess: () => {
      invalidate();
      setAddingFor(null);
      setSelectedHousehold("");
    },
  });

  const removeMutation = useMutation({
    mutationFn: ({ userId, householdId }: { userId: string; householdId: string }) =>
      removeUserMembership(userId, householdId),
    onSuccess: invalidate,
  });

  if (isError || !users) return null;

  const pending = purgeMutation.isPending || addMutation.isPending || removeMutation.isPending;
  const error = purgeMutation.error ?? addMutation.error ?? removeMutation.error;

  function handlePurge(user: AdminUserSummary) {
    const detail =
      user.memberships.length > 0
        ? ` They currently belong to: ${user.memberships.map((m) => m.household_name).join(", ")}.`
        : " This account has no household memberships.";
    if (window.confirm(`Permanently delete ${user.email}?${detail} This cannot be undone.`)) {
      purgeMutation.mutate(user.id);
    }
  }

  function submitAdd(userId: string) {
    if (!selectedHousehold) return;
    addMutation.mutate({ userId, householdId: selectedHousehold, role: selectedRole });
  }

  return (
    <section className="panel">
      <span className="panel-eyebrow">Instance admin</span>
      <h2>User management</h2>
      <p>
        Every user account on this instance, including orphaned ones (a real account with no household to log
        into). Add an orphan to a household directly to fix it, or purge accounts that shouldn&rsquo;t exist.
      </p>
      {error && <StatusMessage>{error instanceof ApiError ? error.message : "Something went wrong."}</StatusMessage>}

      <ul className="admin-household-list">
        {users.map((user) => (
          <li key={user.id}>
            <div className="admin-household-header">
              <strong>{user.display_name}</strong>
              <span className="member-email">{user.email}</span>
              {user.is_instance_admin && <span className="panel-eyebrow">Admin</span>}
              {user.memberships.length === 0 && <span className="panel-eyebrow">Orphaned</span>}
              <button
                type="button"
                className="danger admin-household-delete"
                title={`Purge ${user.email}`}
                aria-label={`Purge ${user.email}`}
                disabled={pending}
                onClick={() => handlePurge(user)}
              >
                ×
              </button>
            </div>

            {user.memberships.length > 0 && (
              <ul className="admin-member-list">
                {user.memberships.map((membership) => (
                  <li key={membership.household_id}>
                    <span>{membership.household_name}</span>
                    <span className="member-role">{membership.role}</span>
                    <button
                      type="button"
                      className="secondary"
                      disabled={pending}
                      onClick={() =>
                        removeMutation.mutate({ userId: user.id, householdId: membership.household_id })
                      }
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {addingFor === user.id ? (
              <div className="inline-form" style={{ marginTop: "8px" }}>
                <select value={selectedHousehold} onChange={(e) => setSelectedHousehold(e.target.value)}>
                  <option value="">Select a household…</option>
                  {households?.map((household) => (
                    <option key={household.id} value={household.id}>
                      {household.name}
                    </option>
                  ))}
                </select>
                <select value={selectedRole} onChange={(e) => setSelectedRole(e.target.value as "owner" | "member")}>
                  <option value="member">Member</option>
                  <option value="owner">Owner</option>
                </select>
                <button type="button" disabled={pending || !selectedHousehold} onClick={() => submitAdd(user.id)}>
                  Add
                </button>
                <button type="button" className="secondary" onClick={() => setAddingFor(null)}>
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="secondary"
                style={{ marginTop: "8px" }}
                disabled={pending}
                onClick={() => {
                  setAddingFor(user.id);
                  setSelectedHousehold("");
                  setSelectedRole("member");
                }}
              >
                Add to household
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
