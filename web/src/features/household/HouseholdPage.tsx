// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createInvite,
  getCurrentHousehold,
  listInvites,
  listMembers,
  removeMember,
  revokeInvite,
} from "../../api/households";
import type { HouseholdRole } from "../../api/types";
import { StatusMessage } from "../../components/StatusMessage";

function inviteLink(token: string): string {
  return `${window.location.origin}/join?token=${encodeURIComponent(token)}`;
}

export function HouseholdPage() {
  const queryClient = useQueryClient();
  const { data: household } = useQuery({ queryKey: ["household"], queryFn: getCurrentHousehold });
  const { data: members, isLoading: membersLoading } = useQuery({ queryKey: ["members"], queryFn: listMembers });
  const isOwner = household?.my_role === "owner";

  const { data: invites } = useQuery({
    queryKey: ["invites"],
    queryFn: listInvites,
    enabled: isOwner,
  });

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<HouseholdRole>("member");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [manualCopyInvite, setManualCopyInvite] = useState<{ id: string; url: string } | null>(null);

  const [lastInvite, setLastInvite] = useState<{ email: string; emailSent: boolean } | null>(null);

  const inviteMutation = useMutation({
    mutationFn: () => createInvite(email, role),
    onSuccess: (invite) => {
      // Report which delivery actually happened rather than assuming the
      // email went out — on an instance with no SMTP relay configured,
      // copying the link is still the only way the invitee hears about this.
      setLastInvite({ email: invite.invited_email, emailSent: invite.email_sent });
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

  function handleInvite(event: FormEvent) {
    event.preventDefault();
    if (email.trim()) inviteMutation.mutate();
  }

  async function handleCopy(invite: { id: string; token: string }) {
    const url = inviteLink(invite.token);
    // The Clipboard API only exists in a secure context (HTTPS, or the
    // special-cased "localhost") -- this app is normally self-hosted and
    // reached over plain HTTP at a LAN address, which is NOT a secure
    // context, so navigator.clipboard is undefined there. Previously this
    // threw an uncaught TypeError the moment the button was clicked and did
    // nothing else, which is exactly what "copy invite link doesn't work"
    // looked like (Vikunja #87). Fall back to showing the link so it can be
    // copied by hand instead of silently failing.
    try {
      if (!navigator.clipboard) throw new Error("Clipboard API unavailable (not a secure context)");
      await navigator.clipboard.writeText(url);
      setManualCopyInvite(null);
      setCopiedId(invite.id);
      setTimeout(() => setCopiedId((current) => (current === invite.id ? null : current)), 2000);
    } catch {
      setCopiedId(null);
      setManualCopyInvite({ id: invite.id, url });
    }
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
              {inviteMutation.isPending ? "Sending…" : "Send invite"}
            </button>
          </form>
          {lastInvite && (
            <StatusMessage>
              {lastInvite.emailSent
                ? `Invite emailed to ${lastInvite.email}.`
                : `Invite created for ${lastInvite.email}, but no email was sent — this instance has no working
                   email relay configured. Copy the link below and send it to them yourself.`}
            </StatusMessage>
          )}

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
                {manualCopyInvite?.id === invite.id && (
                  <div className="invite-copy-fallback">
                    <StatusMessage>Couldn&rsquo;t copy automatically — select and copy the link below.</StatusMessage>
                    <input
                      type="text"
                      readOnly
                      value={manualCopyInvite.url}
                      onFocus={(e) => e.currentTarget.select()}
                      ref={(el) => el?.focus()}
                    />
                  </div>
                )}
              </li>
            ))}
          </ul>
          {invites?.length === 0 && <p>No invites yet.</p>}
        </>
      )}
    </div>
  );
}
