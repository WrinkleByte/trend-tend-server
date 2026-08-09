import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getInstanceSettings, updateInstanceSettings, type InstanceSettingsUpdate } from "../../api/instanceSettings";

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

  // 403 (not the instance admin) is the expected, common case for most
  // logged-in users — this section simply isn't for them, not an error to
  // surface.
  if (isError || !settings) return null;

  return (
    <section>
      <h2>Email (SMTP)</h2>
      <p>
        Configure an SMTP relay so &ldquo;forgot password&rdquo; emails can actually be delivered. Without this,
        password resets still work, but only if an admin manually retrieves the link from the server logs.
      </p>
      <form className="settings-form" onSubmit={handleSubmit}>
        <label>
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
        <label>
          Username
          <input value={form.smtp_username ?? ""} onChange={(e) => setForm({ ...form, smtp_username: e.target.value })} />
        </label>
        <label>
          Password
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder={settings.smtp_password_set ? "Unchanged — leave blank to keep it" : "Not set"}
          />
        </label>
        <label>
          <input
            type="checkbox"
            checked={form.smtp_use_tls ?? true}
            onChange={(e) => setForm({ ...form, smtp_use_tls: e.target.checked })}
          />
          Use TLS
        </label>
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
