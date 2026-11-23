// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  assignApiToken,
  createApiToken,
  deleteApiToken,
  listApiTokens,
  revokeApiToken,
} from "../../api/apiTokens";
import { getCurrentHousehold, listMembers } from "../../api/households";
import { StatusMessage } from "../../components/StatusMessage";
import { PairingCodeReveal } from "./PairingCodeReveal";
import { PairingUrlSection } from "./PairingUrlSection";
import { formatDateTime } from "../../lib/format";
import { deviceRowState, invalidateTokenLists, tokenActions } from "./tokenActions";

/** The "API Tokens" settings category — pairing-URL config plus token
 * generate/list/revoke/delete. Was the whole /settings page before the
 * left-sidebar category split; PairingUrlSection stays paired with this
 * (not Households) since it only ever affects the QR code generated here. */
export function ApiTokensPage() {
  const queryClient = useQueryClient();
  const { data: tokens, isLoading } = useQuery({ queryKey: ["api-tokens"], queryFn: listApiTokens });
  const [name, setName] = useState("");
  const [justCreated, setJustCreated] = useState<string | null>(null);

  // Owners can move a key to another member (Vikunja #165): the phone it's
  // already paired on becomes that person's, no re-pairing.
  const { data: household } = useQuery({ queryKey: ["household"], queryFn: getCurrentHousehold });
  const isOwner = household?.my_role === "owner";
  const { data: members } = useQuery({ queryKey: ["members"], queryFn: listMembers, enabled: isOwner });
  const otherMembers = members?.filter((m) => m.user_id !== household?.my_user_id) ?? [];
  const [assignTarget, setAssignTarget] = useState<Record<string, string>>({});
  const [assignedNote, setAssignedNote] = useState<string | null>(null);

  const assignMutation = useMutation({
    mutationFn: ({ tokenId, userId }: { tokenId: string; userId: string }) => assignApiToken(tokenId, userId),
    onSuccess: (token, { userId }) => {
      const who = members?.find((m) => m.user_id === userId)?.display_name ?? "them";
      setAssignedNote(
        `\u201c${token.name}\u201d now belongs to ${who}. A device paired with it syncs as ${who} from its next sync; it now appears under ${who}\u2019s devices on the Household page.`,
      );
      queryClient.invalidateQueries({ queryKey: ["api-tokens"] });
      queryClient.invalidateQueries({ queryKey: ["member-api-tokens"] });
    },
  });

  const createMutation = useMutation({
    mutationFn: () => createApiToken(name),
    onSuccess: (token) => {
      setJustCreated(token.token);
      setName("");
      queryClient.invalidateQueries({ queryKey: ["api-tokens"] });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => revokeApiToken(id),
    // Both listings, not just this one: a code revoked here is also listed under that member's
    // devices on the Household page, which otherwise keeps offering Revoke for a key that is
    // already revoked (Vikunja #196).
    onSuccess: () => invalidateTokenLists(queryClient),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteApiToken(id),
    onSuccess: () => invalidateTokenLists(queryClient),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (name.trim()) createMutation.mutate();
  }

  return (
    <div>
      <PairingUrlSection />

      <section className="panel">
        <h2>Pair a phone or tablet</h2>
        <p>
          Create a pairing code here, then scan its QR code (or type the code) in the app&rsquo;s sync
          settings. Each device gets its own code, so a lost phone can be removed without affecting the others.
        </p>

        {justCreated && <PairingCodeReveal token={justCreated} onDone={() => setJustCreated(null)} />}

        <form className="inline-form" onSubmit={handleSubmit}>
          <input placeholder="Token name, e.g. My iPhone" value={name} onChange={(e) => setName(e.target.value)} />
          <button type="submit" disabled={createMutation.isPending}>
            Create pairing code
          </button>
        </form>

        {assignedNote && <StatusMessage>{assignedNote}</StatusMessage>}
        {assignMutation.isError && <StatusMessage>{(assignMutation.error as Error).message}</StatusMessage>}
        {/* Without these a failed revoke or delete looked like a dead button: the row stayed put
            and nothing said why (Vikunja #196). */}
        {revokeMutation.isError && <StatusMessage>Could not revoke that code: {(revokeMutation.error as Error).message}</StatusMessage>}
        {deleteMutation.isError && <StatusMessage>Could not delete that code: {(deleteMutation.error as Error).message}</StatusMessage>}
        {isLoading && <p>Loading…</p>}
        <ul className="token-list">
          {tokens?.map((token) => {
            const actions = tokenActions(token, true);
            const state = deviceRowState(token);
            return (
            <li key={token.id}>
              <span className="token-label">
                <span className="token-name">{token.name}</span>
                {token.created_by_name && (
                  <span className="token-created-by">set up by {token.created_by_name}</span>
                )}
              </span>
              {/* Same wording and formatting the Household page uses. The raw UTC stamp with
                  microseconds was long enough by itself to push Revoke onto a line of its own. */}
              <span className={state === "revoked" ? "token-status token-revoked" : "token-status"}>
                {state === "revoked"
                  ? "Revoked"
                  : state === "used"
                    ? `Last used ${formatDateTime(token.last_used_at)}`
                    : "Not used yet"}
              </span>
              {!token.revoked_at && isOwner && otherMembers.length > 0 && (
                <span className="token-assign">
                  <select
                    aria-label={`Assign ${token.name} to`}
                    value={assignTarget[token.id] ?? ""}
                    onChange={(e) => setAssignTarget({ ...assignTarget, [token.id]: e.target.value })}
                  >
                    <option value="">Assign to&hellip;</option>
                    {otherMembers.map((m) => (
                      <option key={m.user_id} value={m.user_id}>
                        {m.display_name}
                        {m.email ? ` (${m.email})` : ""}
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
              )}
              {(actions.canRevoke || actions.canDelete) && (
                <span className="token-actions">
                  {actions.canRevoke && (
                    <button
                      type="button"
                      className="danger"
                      disabled={revokeMutation.isPending}
                      onClick={() => revokeMutation.mutate(token.id)}
                    >
                      Revoke
                    </button>
                  )}
                  {actions.canDelete && (
                    <button
                      type="button"
                      className="danger"
                      disabled={deleteMutation.isPending}
                      onClick={() => deleteMutation.mutate(token.id)}
                    >
                      Delete
                    </button>
                  )}
                </span>
              )}
            </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
