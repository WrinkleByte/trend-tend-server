// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import type { ReactNode } from "react";
import type { IconName } from "../components/ui/Icon";

/** Where a feature's menu entry appears: "primary" is the main navigation
 * (sidebar on desktop, bottom bar on phones); "account" is the quieter group
 * for occasional tasks (bottom of the sidebar, the phone's More sheet). */
export type NavPlacement = "primary" | "account";

export interface NavEntry {
  to: string;
  label: string;
  icon: IconName;
  placement: NavPlacement;
  /** Match the path exactly (needed for "/", which prefixes everything). */
  end?: boolean;
  /** Also show this entry as current under this path prefix, for pages
   * that belong to the feature but live at a different address. */
  alsoActiveUnder?: string;
}

export interface FeatureRoute {
  path: string;
  element: ReactNode;
}

/** Everything the app shell needs to know about one feature area. A feature
 * declares its pages and (optionally) its menu entry here; App.tsx builds the
 * route tree and Layout.tsx builds the navigation from the list in
 * features.ts. Adding a feature is one feature.tsx plus one line there. */
export interface FeatureModule {
  id: string;
  routes: FeatureRoute[];
  nav?: NavEntry;
}
