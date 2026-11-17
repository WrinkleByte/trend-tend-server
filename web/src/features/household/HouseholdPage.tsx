// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { assignApiToken } from "../../api/apiTokens";
import {
  addAppOnlyMember,
  createInvite,
  createMemberApiToken,
  getCurrentHousehold,
  listInvites,
  listMemberApiTokens,
  listMembers,
  removeMember,
  revokeInvite,
  revokeMemberApiToken,
} from "../../api/households";
import type { HouseholdMember, HouseholdRole } from "../../api/types";
import { updateMyDisplayName } from "../../api/users";
import { StatusMessage } from "../../components/StatusMessage";
import { formatDateTime } from "../../lib/format";
import { PairingCodeReveal } from "../settings/PairingCodeReveal";
import { useHouseholdMembers } from "./useHouseholdMembers";

/** Who you are in this household, and changing your own name (Vikunja
 * #164): with several people syncing, it isn't always obvious which member
 * this sign-in is. */
function YouInThisHousehold({ me, role }: { me: HouseholdMember; role: HouseholdRole }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(me.display_name);
  const mutation = useMutation({
    mutationFn: () => updateMyDisplayName(name.trim()),
    onSuccess: () => {
      setEditing(false);
      queryClient.invalidateQueries({ queryKey: ["members"] });
    },
  });
  return (
    <section className="you-in-household" aria-label="You">
      <h2>You</h2>
      {!editing ? (
        <p>
          Signed in as <strong>{me.display_name}</strong>
          {me.email ? ` \u00b7 ${me.email}` : ""}
          {` \u00b7 ${role} `}
          <button
            type="button"
            onClick={() => {
              setName(me.display_name);
              setEditing(true);
            }}
          >
            Change name
          </button>
        </p>
      ) : (
        <form
          className="inline-form"
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            if (name.trim()) mutation.mutate();
          }}
        >
          <input
            aria-label="Your name"
            value={name}
            maxLength={200}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <button type="submit" disabled={mutation.isPending || !name.trim()}>
            Save
          </button>
          <button type="button" onClick={() => setEditing(false)}>
            Cancel
          </button>
        </form>
      )}
      <p className="field-hint">Everyone in the household sees this name.</p>
      {mutation.isError && <StatusMessage>{(mutation.error as Error).message}</StatusMessage>}
    </section>
  );
}

/** One member's devices (their API keys, whoever made them), for the owner:
 * pair a new phone or tablet as this member, or revoke a lost one. Pairing
 * a device for someone means it syncs as them -- the point for a family
 * where not everyone wants a web account (Vikunja #165). */
function MemberDevices({
  member,
  isSelf,
  members,
}: {
  member: HouseholdMember;
  isSelf: boolean;
  members: HouseholdMember[];
}) {
  const queryClient = useQueryClient();
  const queryKey = ["member-api-tokens", member.user_id];
  const { data: tokens } = useQuery({ queryKey, queryFn: () => listMemberApiTokens(member.user_id) });
  const [deviceName, setDeviceName] = useState("");
  const [justCreated, setJustCreated] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      createMemberApiToken(member.user_id, deviceName.trim() || `${member.display_name}\u2019s phone`),
    onSuccess: (token) => {
      setJustCreated(token.token);
      setDeviceName("");
      queryClient.invalidateQueries({ queryKey });
    },
  });
  const revokeMutation = useMutation({
    mutationFn: (tokenId: string) => revokeMemberApiToken(member.user_id, tokenId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });
  // Move a device to someone else, including back to yourself: the key's
  // device becomes theirs on its next sync, no re-pairing.
  const [assignTarget, setAssignTarget] = useState<Record<string, string>>({});
  const assignMutation = useMutation({
    mutationFn: ({ tokenId, userId }: { tokenId: string; userId: string }) => assignApiToken(tokenId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["member-api-tokens"] });
      queryClient.invalidateQueries({ queryKey: ["api-tokens"] });
    },
  });
  const { pickerMembers, pickerLabel } = useHouseholdMembers();
  const assignable = (pickerMembers.length ? pickerMembers : members).filter((m) => m.user_id !== member.user_id);

  const active = tokens?.filter((t) => !t.revoked_at) ?? [];
  return (
    <div className="member-devices">
      {justCreated && (
        <PairingCodeReveal
          token={justCreated}
          forName={isSelf ? undefined : member.display_name}
          onDone={() => setJustCreated(null)}
        />
      )}
      {assignMutation.isError && <StatusMessage>{(assignMutation.error as Error).message}</StatusMessage>}
      <form
        className="inline-form"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          createMutation.mutate();
        }}
      >
        <input
          placeholder={`Device name, e.g. ${member.display_name}\u2019s iPhone`}
          value={deviceName}
          onChange={(e) => setDeviceName(e.target.value)}
        />
        <button type="submit" disabled={createMutation.isPending}>
          Pair a device
        </button>
      </form>
      {active.length > 0 && (
        // A table, with shaded rows and readable times: as a run-on list,
        // several devices were hard to tell apart (owner, 2026-11-16).
        <div className="device-table-wrap">
        <table className="device-table">
          <thead>
            <tr>
              <th scope="col">Device</th>
              <th scope="col">Last synced</th>
              {assignable.length > 0 && <th scope="col">Move to</th>}
              <th scope="col" className="device-actions">
                <span className="visually-hidden">Revoke</span>
              </th>
            </tr>
          </thead>
          <tbody>
          {active.map((token) => (
            <tr key={token.id}>
              <td className="device-name">{token.name}</td>
              <td title={token.last_used_at ?? undefined}>
                {token.last_used_at ? formatDateTime(token.last_used_at) : <span className="device-unused">Not used yet</span>}
              </td>
              {assignable.length > 0 && (
                <td>
                <span className="token-assign">
                  <select
                    aria-label={`Move ${token.name} to`}
                    value={assignTarget[token.id] ?? ""}
                    onChange={(e) => setAssignTarget({ ...assignTarget, [token.id]: e.target.value })}
                  >
                    <option value="">Assign to&hellip;</option>
                    {assignable.map((m) => (
                      <option key={m.user_id} value={m.user_id}>
                        {pickerLabel(m)}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={!assignTarget[token.id] || assignMutation.isPending}
                    onClick={() => assignMutation.mutate({ tokenId: token.id, userId: assignTarget[token.id] })}
                  >
                    Assign
                  </button>
                </span>
                </td>
              )}
              <td className="device-actions">
                <button type="button" className="danger" onClick={() => revokeMutation.mutate(token.id)}>
                  Revoke
                </button>
              </td>
            </tr>
          ))}
          </tbody>
        </table>
        </div>
      )}
    </div>
  );
}

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

  const [newMemberName, setNewMemberName] = useState("");
  const [newMemberEmail, setNewMemberEmail] = useState("");
  const [openDevicesFor, setOpenDevicesFor] = useState<string | null>(null);

  const addMemberMutation = useMutation({
    mutationFn: () => addAppOnlyMember(newMemberName.trim(), newMemberEmail.trim() || null),
    onSuccess: (member) => {
      setNewMemberName("");
      setNewMemberEmail("");
      // Straight to pairing their phone: that's what they were added for.
      setOpenDevicesFor(member.user_id);
      queryClient.invalidateQueries({ queryKey: ["members"] });
    },
  });

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

      {household && members?.find((m) => m.user_id === household.my_user_id) && (
        <YouInThisHousehold
          key={household.my_user_id}
          me={members.find((m) => m.user_id === household.my_user_id)!}
          role={household.my_role}
        />
      )}

      <h2>Members</h2>
      {membersLoading && <p>Loading…</p>}
      <ul className="household-member-list">
        {members?.map((member) => (
          <li key={member.user_id}>
            <span>{member.display_name}</span>
            <span className="member-email">{member.email || (member.has_login ? "" : "App only")}</span>
            <span className="member-role">{member.role}</span>
            {isOwner && (
              <button
                type="button"
                onClick={() => setOpenDevicesFor(openDevicesFor === member.user_id ? null : member.user_id)}
              >
                {openDevicesFor === member.user_id ? "Hide devices" : "Devices"}
              </button>
            )}
            {isOwner && member.role !== "owner" && (
              <button type="button" className="danger" onClick={() => removeMutation.mutate(member.user_id)}>
                Remove
              </button>
            )}
            {isOwner && openDevicesFor === member.user_id && (
              <MemberDevices
                member={member}
                isSelf={member.user_id === household?.my_user_id}
                members={members ?? []}
              />
            )}
          </li>
        ))}
      </ul>

      {isOwner && (
        <>
          <h2>Add a family member</h2>
          <p>
            For someone who will use the app but doesn&rsquo;t need a web account. You pair their phone for them, and
            it syncs as them. Add their email if they might want to sign in on the web later (they can use
            &ldquo;Forgot password&rdquo;).
          </p>
          <form
            className="inline-form"
            onSubmit={(event: FormEvent) => {
              event.preventDefault();
              if (newMemberName.trim()) addMemberMutation.mutate();
            }}
          >
            <input
              placeholder="Name"
              value={newMemberName}
              onChange={(e) => setNewMemberName(e.target.value)}
              required
            />
            <input
              type="email"
              placeholder="Email (optional)"
              value={newMemberEmail}
              onChange={(e) => setNewMemberEmail(e.target.value)}
            />
            <button type="submit" disabled={addMemberMutation.isPending}>
              Add member
            </button>
          </form>
          {addMemberMutation.isError && <StatusMessage>{(addMemberMutation.error as Error).message}</StatusMessage>}

          <h2>Invite someone</h2>
          <p>For someone who wants their own web sign-in.</p>
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
