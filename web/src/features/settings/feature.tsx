// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import type { FeatureModule } from "../../app/featureTypes";
import { SettingsPage } from "./SettingsPage";

export const settingsFeature: FeatureModule = {
  id: "settings",
  nav: { to: "/settings", label: "Settings", icon: "settings", placement: "account" },
  routes: [
    { path: "/settings", element: <SettingsPage /> },
    { path: "/settings/:section", element: <SettingsPage /> },
  ],
};
