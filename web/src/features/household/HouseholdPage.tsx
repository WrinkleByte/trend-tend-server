import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  createInvite,
  deleteHousehold,
  getCurrentHousehold,
  listInvites,
  listMembers,
  removeMember,
  revokeInvite,
} from "../../api/households";
import type { HouseholdRole } from "../../api/types";
import { useAuthStore } from "../../auth/authStore";

function inviteLink(token: string): string {
  return `${window.location.origin}/join?token=${encodeURIComponent(token)}`;
}

export function HouseholdPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const clearAuth = useAuthStore((s) => s.clear);
  const { data: household } = useQuery({ queryKey: ["household"], queryFn: getCurrentHousehold });
  const { data: members, isLoading: membersLoading } = useQuery({ queryKey: ["members"], queryFn: listMembers });
  const isOwner = household?.my_role === "owner";
  const [confirmDeleteText, setConfirmDeleteText] = useState("");
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const { data: invites } = useQuery({
    queryKey: ["invites"],
    queryFn: listInvites,
    enabled: isOwner,
  });

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<HouseholdRole>("member");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const inviteMutation = useMutation({
    mutationFn: () => createInvite(email, role),
    onSuccess: () => {
      setEmail("");
      queryClient.invalidateQueries({ queryKey: ["invites"] });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => revokeInvite(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["invites"] }),
  });

  const removeMutation = useMutation({
    mutationFn: (userId: string) => removeMember(userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["members"] }),
  });

  const deleteHouseholdMutation = useMutation({
    mutationFn: () => deleteHousehold(),
    onSuccess: () => {
      // Every member's session for this household is invalid the moment
      // it's gone, including the owner's who just deleted it — there's no
      // "switch to another household" here, just a clean logout. Anyone
      // with a membership elsewhere just logs back in normally.
      clearAuth();
      navigate("/login");
    },
  });

  function handleInvite(event: FormEvent) {
    event.preventDefault();
    if (email.trim()) inviteMutation.mutate();
  }

  async function handleCopy(invite: { id: string; token: string }) {
    await navigator.clipboard.writeText(inviteLink(invite.token));
    setCopiedId(invite.id);
    setTimeout(() => setCopiedId((current) => (current === invite.id ? null : current)), 2000);
  }

  return (
    <div>
      <h1>Household{household ? `: ${household.name}` : ""}</h1>

      <h2>Members</h2>
      {membersLoading && <p>Loading…</p>}
      <ul className="household-member-list">
        {members?.map((member) => (
          <li key={member.user_id}>
            <span>{member.display_name}</span>
            <span className="member-email">{member.email}</span>
            <span className="member-role">{member.role}</span>
            {isOwner && member.role !== "owner" && (
              <button type="button" className="danger" onClick={() => removeMutation.mutate(member.user_id)}>
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>

      {isOwner && (
        <>
          <h2>Invite someone</h2>
          <form className="inline-form" onSubmit={handleInvite}>
            <input
              type="email"
              placeholder="Email address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <select value={role} onChange={(e) => setRole(e.target.value as HouseholdRole)}>
              <option value="member">Member</option>
              <option value="owner">Owner</option>
            </select>
            <button type="submit" disabled={inviteMutation.isPending}>
              Create invite
            </button>
          </form>

          <h2>Pending &amp; past invites</h2>
          <ul className="invite-list">
            {invites?.map((invite) => (
              <li key={invite.id}>
                <span>{invite.invited_email}</span>
                <span className="member-role">{invite.role}</span>
                <span className={`invite-status invite-status-${invite.status}`}>{invite.status}</span>
                {invite.status === "pending" && (
                  <>
                    <button type="button" onClick={() => handleCopy(invite)}>
                      {copiedId === invite.id ? "Copied!" : "Copy invite link"}
                    </button>
                    <button type="button" className="danger" onClick={() => revokeMutation.mutate(invite.id)}>
                      Revoke
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
          {invites?.length === 0 && <p>No invites yet.</p>}
        </>
      )}

      {isOwner && household && (
        <section className="panel panel-danger">
          <h2>Danger zone</h2>
          {!confirmingDelete ? (
            <button type="button" className="danger" onClick={() => setConfirmingDelete(true)}>
              Delete household
            </button>
          ) : (
            <div className="notice notice-error">
              <p>
                This permanently deletes <strong>{household.name}</strong> — every asset, service record, fuel
                and trip log, schedule, and member. Every other member (including any co-owners) loses access
                immediately. This cannot be undone.
              </p>
              <label style={{ marginTop: "12px" }}>
                Type <strong>{household.name}</strong> to confirm
                <input value={confirmDeleteText} onChange={(e) => setConfirmDeleteText(e.target.value)} />
              </label>
              {deleteHouseholdMutation.isError && (
                <p className="form-error">Something went wrong — the household was not deleted.</p>
              )}
              <div className="form-actions" style={{ marginTop: "12px" }}>
                <button
                  type="button"
                  className="danger"
                  disabled={confirmDeleteText !== household.name || deleteHouseholdMutation.isPending}
                  onClick={() => deleteHouseholdMutation.mutate()}
                >
                  {deleteHouseholdMutation.isPending ? "Deleting…" : "Permanently delete household"}
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    setConfirmingDelete(false);
                    setConfirmDeleteText("");
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
