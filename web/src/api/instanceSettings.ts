// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { apiFetch } from "./client";

export interface InstanceSettings {
  smtp_enabled: boolean;
  smtp_host: string | null;
  smtp_port: number | null;
  smtp_username: string | null;
  smtp_use_tls: boolean;
  smtp_from_address: string | null;
  smtp_password_set: boolean;
  public_api_url: string | null;
  allow_self_registration: boolean;
}

export interface InstanceSettingsUpdate {
  smtp_enabled?: boolean;
  smtp_host?: string;
  smtp_port?: number;
  smtp_username?: string;
  // Omit to leave the stored password unchanged; pass "" to clear it — see
  // backend app/schemas/instance_settings.py's doc comment.
  smtp_password?: string;
  smtp_use_tls?: boolean;
  smtp_from_address?: string;
  public_api_url?: string;
  allow_self_registration?: boolean;
}

export function getInstanceSettings(): Promise<InstanceSettings> {
  return apiFetch("/instance-settings");
}

export function updateInstanceSettings(input: InstanceSettingsUpdate): Promise<InstanceSettings> {
  return apiFetch("/instance-settings", { method: "PUT", body: JSON.stringify(input) });
}
