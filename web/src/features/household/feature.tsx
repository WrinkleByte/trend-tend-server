// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import type { FeatureModule } from "../../app/featureTypes";
import { HouseholdPage } from "./HouseholdPage";

export const householdFeature: FeatureModule = {
  id: "household",
  nav: { to: "/household", label: "Household", icon: "household", placement: "primary" },
  routes: [{ path: "/household", element: <HouseholdPage /> }],
};
