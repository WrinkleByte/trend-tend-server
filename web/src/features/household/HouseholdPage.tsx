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
  wipeHouseholdData,
} from "../../api/households";
import type { HouseholdRole } from "../../api/types";
import { useAuthStore } from "../../auth/authStore";
import { StatusMessage } from "../../components/StatusMessage";

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
  const [confirmWipeText, setConfirmWipeText] = useState("");
  const [wipeAcknowledged, setWipeAcknowledged] = useState(false);
  const [confirmingWipe, setConfirmingWipe] = useState(false);
  const [wiped, setWiped] = useState(false);

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

  const wipeHouseholdMutation = useMutation({
    mutationFn: () => wipeHouseholdData(),
    onSuccess: () => {
      // Unlike delete, the session and household survive — just refetch
      // everything asset-scoped so stale cached data doesn't linger on
      // whatever page the owner navigates to next. The 1-element key
      // prefixes below partial-match every per-asset-scoped query
      // regardless of asset id, same pattern ImportPage's restore-invalidation
      // already relies on.
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      queryClient.invalidateQueries({ queryKey: ["maintenance-records"] });
      queryClient.invalidateQueries({ queryKey: ["maintenance-schedules"] });
      queryClient.invalidateQueries({ queryKey: ["trip-logs"] });
      queryClient.invalidateQueries({ queryKey: ["fuel-logs"] });
      setConfirmingWipe(false);
      setConfirmWipeText("");
      setWipeAcknowledged(false);
      setWiped(true);
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

          <h3>Wipe all data</h3>
          {wiped && !confirmingWipe && (
            <p className="notice notice-success">
              All data has been wiped. {household.name} still exists — assets, logs, and records just start
              empty again.
            </p>
          )}
          {!confirmingWipe ? (
            <button type="button" className="danger" onClick={() => setConfirmingWipe(true)}>
              Wipe all data
            </button>
          ) : (
            <div className="notice notice-error">
              <p>
                This permanently deletes every asset, service record, schedule, fuel log, trip log, and photo in{" "}
                <strong>{household.name}</strong>. The household itself, its members, and their logins are
                <strong> not</strong> affected — this is for starting over, not leaving. This cannot be undone.
              </p>
              <label style={{ marginTop: "12px" }}>
                Type <strong>{household.name}</strong> to confirm
                <input value={confirmWipeText} onChange={(e) => setConfirmWipeText(e.target.value)} />
              </label>
              <label className="check-label" style={{ marginTop: "12px" }}>
                <input
                  type="checkbox"
                  checked={wipeAcknowledged}
                  onChange={(e) => setWipeAcknowledged(e.target.checked)}
                />
                I understand every asset and record will be permanently deleted and this cannot be undone
              </label>
              {wipeHouseholdMutation.isError && (
                <StatusMessage>Something went wrong — no data was wiped.</StatusMessage>
              )}
              <div className="form-actions" style={{ marginTop: "12px" }}>
                <button
                  type="button"
                  className="danger"
                  disabled={
                    confirmWipeText !== household.name || !wipeAcknowledged || wipeHouseholdMutation.isPending
                  }
                  onClick={() => wipeHouseholdMutation.mutate()}
                >
                  {wipeHouseholdMutation.isPending ? "Wiping…" : "Permanently wipe all data"}
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    setConfirmingWipe(false);
                    setConfirmWipeText("");
                    setWipeAcknowledged(false);
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          <h3 style={{ marginTop: "24px" }}>Delete household</h3>
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
                <StatusMessage>Something went wrong — the household was not deleted.</StatusMessage>
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
