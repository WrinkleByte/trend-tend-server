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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["api-tokens"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteApiToken(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["api-tokens"] }),
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
        {isLoading && <p>Loading…</p>}
        <ul className="token-list">
          {tokens?.map((token) => (
            <li key={token.id}>
              <span>
                {token.name}
                {token.created_by_name && (
                  <span className="token-created-by"> (set up by {token.created_by_name})</span>
                )}
              </span>
              <span>
                {token.revoked_at
                  ? "Revoked"
                  : token.last_used_at
                    ? `Last used ${token.last_used_at}`
                    : "Never used"}
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
              {!token.revoked_at && (
                <button type="button" className="danger" onClick={() => revokeMutation.mutate(token.id)}>
                  Revoke
                </button>
              )}
              {token.revoked_at && (
                <button type="button" className="danger" onClick={() => deleteMutation.mutate(token.id)}>
                  Delete
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
