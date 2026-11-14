// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import type { ReactNode } from "react";
import { AdminHouseholdsSection } from "./AdminHouseholdsSection";
import { ApiTokensPage } from "./ApiTokensPage";
import { DangerZoneSection } from "./DangerZoneSection";
import { DisplaySection } from "./DisplaySection";
import { InstanceSettingsSection } from "./InstanceSettingsSection";
import { RegistrationSection } from "./RegistrationSection";
import { UserManagementSection } from "./UserManagementSection";

export interface SettingsSection {
  /** The address: /settings/<id>. */
  id: string;
  label: string;
  element: ReactNode;
}

export interface SettingsGroup {
  label: string;
  /** Shown only to people who administer this server. */
  adminOnly?: boolean;
  sections: SettingsSection[];
}

/** Settings, grouped by who they're for. To add a settings page, add an
 * entry here: the sidebar, the address and the admin gating follow. */
export const SETTINGS_GROUPS: SettingsGroup[] = [
  {
    label: "You",
    sections: [
      { id: "devices", label: "Phones & devices", element: <ApiTokensPage /> },
      { id: "display", label: "Display", element: <DisplaySection /> },
    ],
  },
  {
    label: "Household",
    sections: [{ id: "danger-zone", label: "Delete data", element: <DangerZoneSection /> }],
  },
  {
    label: "Server",
    adminOnly: true,
    sections: [
      { id: "email", label: "Email (SMTP)", element: <InstanceSettingsSection /> },
      { id: "registration", label: "Sign-ups", element: <RegistrationSection /> },
      { id: "households", label: "Households", element: <AdminHouseholdsSection /> },
      { id: "users", label: "Users", element: <UserManagementSection /> },
    ],
  },
];

export const DEFAULT_SETTINGS_SECTION = "devices";
