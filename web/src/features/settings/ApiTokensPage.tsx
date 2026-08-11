import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { createApiToken, listApiTokens, revokeApiToken } from "../../api/apiTokens";
import { useAssetPhotosEnabled } from "./assetPhotosSetting";
import { InstanceSettingsSection } from "./InstanceSettingsSection";

function buildPairingPayload(server: string, token: string): string {
  return JSON.stringify({ v: 1, server, token });
}

export function ApiTokensPage() {
  const queryClient = useQueryClient();
  const { data: tokens, isLoading } = useQuery({ queryKey: ["api-tokens"], queryFn: listApiTokens });
  const [name, setName] = useState("");
  const [justCreated, setJustCreated] = useState<string | null>(null);
  const [assetPhotosEnabled, setAssetPhotosEnabled] = useAssetPhotosEnabled();

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

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (name.trim()) createMutation.mutate();
  }

  return (
    <div>
      <h1>Settings</h1>

      <InstanceSettingsSection />

      <h2>Preferences</h2>
      <label style={{ display: "block", marginBottom: "16px" }}>
        <input
          type="checkbox"
          checked={assetPhotosEnabled}
          onChange={(e) => setAssetPhotosEnabled(e.target.checked)}
          style={{ marginRight: "8px" }}
        />
        Show asset profile photos
      </label>

      <h2>API tokens</h2>
      <p>
        Pair a mobile app to this household by generating a token here and entering it — or scanning the QR
        code below — in the app&rsquo;s sync settings.
      </p>

      {justCreated && (
        <div className="token-reveal">
          <p>Copy this token now — it won&rsquo;t be shown again.</p>
          <code>{justCreated}</code>
          <p>Or scan this code from the mobile app&rsquo;s pairing screen:</p>
          <QRCodeSVG value={buildPairingPayload(window.location.origin, justCreated)} size={200} />
          <button type="button" onClick={() => setJustCreated(null)}>
            Done
          </button>
        </div>
      )}

      <form className="inline-form" onSubmit={handleSubmit}>
        <input placeholder="Token name, e.g. My iPhone" value={name} onChange={(e) => setName(e.target.value)} />
        <button type="submit" disabled={createMutation.isPending}>
          Generate token
        </button>
      </form>

      {isLoading && <p>Loading…</p>}
      <ul className="token-list">
        {tokens?.map((token) => (
          <li key={token.id}>
            <span>{token.name}</span>
            <span>
              {token.revoked_at
                ? "Revoked"
                : token.last_used_at
                  ? `Last used ${token.last_used_at}`
                  : "Never used"}
            </span>
            {!token.revoked_at && (
              <button type="button" className="danger" onClick={() => revokeMutation.mutate(token.id)}>
                Revoke
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
