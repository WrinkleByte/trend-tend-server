// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import type { FeatureModule } from "../../app/featureTypes";
import { AssetDetailPage } from "./AssetDetailPage";
import { AssetsPage } from "./AssetsPage";

export const assetsFeature: FeatureModule = {
  id: "assets",
  // The list can't live at /assets: the built app's static files are served
  // from the real directory /assets/, so reloading the page there gets the
  // web server's directory handling instead of the app. Individual assets
  // (/assets/<id>) are unaffected and keep their long-standing addresses.
  nav: { to: "/inventory", label: "Assets", icon: "assets", placement: "primary", alsoActiveUnder: "/assets/" },
  routes: [
    { path: "/inventory", element: <AssetsPage /> },
    { path: "/assets/:id/:tab?", element: <AssetDetailPage /> },
  ],
};
