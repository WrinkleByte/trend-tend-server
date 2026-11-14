// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getInstanceSettings, updateInstanceSettings } from "../../api/instanceSettings";

/**
 * Only ever visible to the instance admin (see backend
 * app/api/deps.py's require_instance_admin) — GET returns 403 for anyone
 * else, and this section just renders nothing rather than an error, same
 * as InstanceSettingsSection's handling elsewhere in this app. Shares the
 * "instance-settings" query cache with that component rather than
 * duplicating the fetch.
 */
export function PairingUrlSection() {
  const queryClient = useQueryClient();
  const { data: settings, isError } = useQuery({
    queryKey: ["instance-settings"],
    queryFn: getInstanceSettings,
    retry: false,
  });

  const [publicApiUrl, setPublicApiUrl] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (settings) setPublicApiUrl(settings.public_api_url ?? "");
  }, [settings]);

  const saveMutation = useMutation({
    mutationFn: () => updateInstanceSettings({ public_api_url: publicApiUrl }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["instance-settings"], updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    saveMutation.mutate();
  }

  if (isError || !settings) return null;

  return (
    <section className="panel">
      <span className="panel-eyebrow">Instance admin</span>
      <h2>Server address for phones</h2>
      <p>
        The address phones use to reach this server. It goes into the pairing QR code below. Leave it blank if
        phones reach the server at the same address as this page; set it if they need a different host or port.
      </p>
      <form className="settings-form" onSubmit={handleSubmit}>
        <label>
          Public API URL
          <input
            value={publicApiUrl}
            onChange={(e) => setPublicApiUrl(e.target.value)}
            placeholder="e.g. http://192.168.1.50:8000"
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
