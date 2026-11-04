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
      <h2>Mobile Pairing URL</h2>
      <p>
        The address a phone can actually reach this server at — used to build the QR code below on the API Tokens
        section. Leave blank if the web app and API share the same address (the default production setup); set it
        explicitly if they&rsquo;re on different ports or hosts, such as this project&rsquo;s local dev/self-hosted
        docker-compose stack (web and API published on different ports) — otherwise the QR code points a pairing
        phone at the wrong service.
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
