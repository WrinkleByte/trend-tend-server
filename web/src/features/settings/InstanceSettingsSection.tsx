// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getInstanceSettings, updateInstanceSettings, type InstanceSettingsUpdate } from "../../api/instanceSettings";

const SMTP_PRESETS = [
  { label: "Gmail", host: "smtp.gmail.com", port: 587 },
  { label: "Yahoo", host: "smtp.mail.yahoo.com", port: 587 },
  { label: "iCloud", host: "smtp.mail.me.com", port: 587 },
  { label: "Proton (Bridge)", host: "127.0.0.1", port: 1025 },
];

// Keyed by the exact host a preset above fills in, so the hint tracks
// whatever's actually in the Host field rather than which button was last
// clicked (matters if the admin edits Host by hand after applying one).
const PROVIDER_HINTS: Record<string, { usernamePlaceholder: string; passwordPlaceholder: string; note: ReactNode }> = {
  "smtp.gmail.com": {
    usernamePlaceholder: "you@gmail.com",
    passwordPlaceholder: "Gmail App Password — not your account password",
    note: (
      <>
        Gmail requires a{" "}
        <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer">
          Google Account App Password
        </a>{" "}
        here, not your normal login password.
      </>
    ),
  },
  "smtp.mail.yahoo.com": {
    usernamePlaceholder: "you@yahoo.com",
    passwordPlaceholder: "Yahoo App Password — not your account password",
    note: (
      <>
        Yahoo requires an app password — Yahoo Account Info →{" "}
        <a href="https://login.yahoo.com/account/security" target="_blank" rel="noreferrer">
          Account Security
        </a>{" "}
        → Generate app password — not your normal login password.
      </>
    ),
  },
  "smtp.mail.me.com": {
    usernamePlaceholder: "you@icloud.com",
    passwordPlaceholder: "App-Specific Password — not your Apple ID password",
    note: (
      <>
        iCloud requires an{" "}
        <a href="https://appleid.apple.com" target="_blank" rel="noreferrer">
          app-specific password
        </a>{" "}
        (Sign-In and Security → App-Specific Passwords), not your Apple ID password. Username and From address must
        both be an email address associated with this Apple ID.
      </>
    ),
  },
  "127.0.0.1": {
    usernamePlaceholder: "your Proton email address",
    passwordPlaceholder: "Bridge-generated password — not your Proton password",
    note: (
      <>
        Proton doesn&rsquo;t expose standard SMTP directly — this only works with{" "}
        <a href="https://proton.me/mail/bridge" target="_blank" rel="noreferrer">
          Proton Mail Bridge
        </a>{" "}
        running and logged in (requires a paid Proton plan), using the password Bridge generates. 127.0.0.1 means
        &ldquo;this container&rdquo; — since the backend runs in Docker, Bridge running on your host machine isn&rsquo;t
        reachable at that address; use <code>host.docker.internal</code> (Docker Desktop) or your host&rsquo;s LAN IP
        instead, and confirm the port Bridge is actually listening on.
      </>
    ),
  },
};

/**
 * Only ever visible to the instance admin (see backend
 * app/api/deps.py's require_instance_admin) — GET returns 403 for anyone
 * else, and this section just renders nothing rather than an error, same
 * as JoinPage's isError handling elsewhere in this app. There's no
 * separate "am I admin" check on the frontend; the 403 itself is the
 * signal.
 */
export function InstanceSettingsSection() {
  const queryClient = useQueryClient();
  const { data: settings, isError } = useQuery({
    queryKey: ["instance-settings"],
    queryFn: getInstanceSettings,
    retry: false,
  });

  const [form, setForm] = useState<InstanceSettingsUpdate>({});
  const [newPassword, setNewPassword] = useState("");
  const [saved, setSaved] = useState(false);

  // Seed the form once settings load — after that, the form is the source
  // of truth for what's being edited, not the server response (which never
  // includes the password anyway).
  useEffect(() => {
    if (settings) {
      setForm({
        smtp_enabled: settings.smtp_enabled,
        smtp_host: settings.smtp_host ?? "",
        smtp_port: settings.smtp_port ?? undefined,
        smtp_username: settings.smtp_username ?? "",
        smtp_use_tls: settings.smtp_use_tls,
        smtp_from_address: settings.smtp_from_address ?? "",
      });
    }
  }, [settings]);

  const saveMutation = useMutation({
    mutationFn: (input: InstanceSettingsUpdate) => updateInstanceSettings(input),
    onSuccess: (updated) => {
      queryClient.setQueryData(["instance-settings"], updated);
      setNewPassword("");
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    saveMutation.mutate({ ...form, ...(newPassword ? { smtp_password: newPassword } : {}) });
  }

  // Fills in host/port/TLS for a known provider; username/from/password are
  // left for the admin to fill in themselves — see PROVIDER_HINTS below for
  // the per-provider credential note shown once a preset is applied.
  function applyPreset(preset: { host: string; port: number }) {
    setForm({ ...form, smtp_enabled: true, smtp_host: preset.host, smtp_port: preset.port, smtp_use_tls: true });
  }

  const provider = PROVIDER_HINTS[form.smtp_host ?? ""];

  // 403 (not the instance admin) is the expected, common case for most
  // logged-in users — this section simply isn't for them, not an error to
  // surface.
  if (isError || !settings) return null;

  return (
    <section className="panel">
      <span className="panel-eyebrow">Instance admin</span>
      <h2>Email (SMTP)</h2>
      <p>
        Configure an SMTP relay so &ldquo;forgot password&rdquo; emails can actually be delivered. Without this,
        password resets still work, but only if an admin manually retrieves the link from the server logs.
      </p>
      <form className="settings-form" onSubmit={handleSubmit}>
        <div className="inline-form">
          {SMTP_PRESETS.map((preset) => (
            <button key={preset.host} type="button" onClick={() => applyPreset(preset)}>
              {preset.label}
            </button>
          ))}
          <span>Fills in host/port/TLS — you still need to add your address and a password below.</span>
        </div>
        <label className="check-label">
          <input
            type="checkbox"
            checked={form.smtp_enabled ?? false}
            onChange={(e) => setForm({ ...form, smtp_enabled: e.target.checked })}
          />
          Enable SMTP
        </label>
        <label>
          Host
          <input
            value={form.smtp_host ?? ""}
            onChange={(e) => setForm({ ...form, smtp_host: e.target.value })}
            placeholder="smtp.example.com"
          />
        </label>
        <label>
          Port
          <input
            type="number"
            value={form.smtp_port ?? ""}
            onChange={(e) => setForm({ ...form, smtp_port: e.target.value ? Number(e.target.value) : undefined })}
            placeholder="587"
          />
        </label>
        <label className="check-label">
          <input
            type="checkbox"
            checked={form.smtp_use_tls ?? true}
            onChange={(e) => setForm({ ...form, smtp_use_tls: e.target.checked })}
          />
          Use TLS
        </label>
        <label>
          Username
          <input
            value={form.smtp_username ?? ""}
            onChange={(e) => setForm({ ...form, smtp_username: e.target.value })}
            placeholder={provider?.usernamePlaceholder ?? "leave blank for no authentication"}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder={
              settings.smtp_password_set
                ? "Unchanged — leave blank to keep it"
                : (provider?.passwordPlaceholder ?? "leave blank for no authentication")
            }
          />
        </label>
        {provider && <p>{provider.note}</p>}
        <label>
          From address
          <input
            type="email"
            value={form.smtp_from_address ?? ""}
            onChange={(e) => setForm({ ...form, smtp_from_address: e.target.value })}
            placeholder="no-reply@example.com"
          />
        </label>
        <button type="submit" disabled={saveMutation.isPending}>
          {saveMutation.isPending ? "Saving…" : "Save"}
        </button>
        {saved && <span> Saved.</span>}
      </form>
    </section>
  );
}
