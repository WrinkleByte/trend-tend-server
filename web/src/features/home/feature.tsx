// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import type { FeatureModule } from "../../app/featureTypes";
import { HomePage } from "./HomePage";

export const homeFeature: FeatureModule = {
  id: "home",
  nav: { to: "/", label: "Home", icon: "home", placement: "primary", end: true },
  routes: [{ path: "/", element: <HomePage /> }],
};
