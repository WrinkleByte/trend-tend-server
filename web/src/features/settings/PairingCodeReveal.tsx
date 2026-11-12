// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useQuery } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { getInstanceSettings } from "../../api/instanceSettings";

function buildPairingPayload(server: string, token: string): string {
  return JSON.stringify({ v: 1, server, token });
}

/** A just-created API key shown once, as text and as the QR code the mobile
 * apps' pairing screen scans. Shared by your own keys (ApiTokensPage) and
 * keys an owner makes for a family member (HouseholdPage). */
export function PairingCodeReveal({
  token,
  forName,
  onDone,
}: {
  token: string;
  /** Whose key this is, when it isn't yours: "Kate". */
  forName?: string;
  onDone: () => void;
}) {
  // 403s for anyone but an instance admin -- React Query just leaves `data`
  // undefined rather than throwing, so this falls through to the
  // window.location.origin fallback below exactly like "not configured" does.
  const { data: instanceSettings } = useQuery({
    queryKey: ["instance-settings"],
    queryFn: getInstanceSettings,
    retry: false,
  });
  const server = instanceSettings?.public_api_url || window.location.origin;

  return (
    <div className="token-reveal">
      {forName ? (
        <p>
          Scan this from the app&rsquo;s pairing screen on {forName}&rsquo;s phone or tablet. That device will sync
          as {forName}. The code is shown only once.
        </p>
      ) : (
        <p>Copy this token now — it won&rsquo;t be shown again.</p>
      )}
      <code>{token}</code>
      {!forName && <p>Or scan this code from the mobile app&rsquo;s pairing screen:</p>}
      <QRCodeSVG value={buildPairingPayload(server, token)} size={200} />
      <button type="button" onClick={onDone}>
        Done
      </button>
    </div>
  );
}
