// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { assetsFeature } from "../features/assets/feature";
import { dataFeature } from "../features/data/feature";
import { homeFeature } from "../features/home/feature";
import { householdFeature } from "../features/household/feature";
import { settingsFeature } from "../features/settings/feature";
import type { FeatureModule } from "./featureTypes";

/** The signed-in app, in menu order. To add a feature: create
 * features/<name>/feature.tsx exporting a FeatureModule and list it here. */
export const FEATURES: FeatureModule[] = [
  homeFeature,
  assetsFeature,
  householdFeature,
  dataFeature,
  settingsFeature,
];
