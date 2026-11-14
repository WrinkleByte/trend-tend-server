// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { Navigate } from "react-router-dom";
import type { FeatureModule } from "../../app/featureTypes";
import { DataPage } from "./DataPage";

export const dataFeature: FeatureModule = {
  id: "data",
  nav: { to: "/data", label: "Import & export", icon: "data", placement: "account" },
  routes: [
    { path: "/data", element: <Navigate to="/data/export" replace /> },
    { path: "/data/:tab", element: <DataPage /> },
    // The pre-shell addresses, kept so bookmarks and docs links still land.
    { path: "/import", element: <Navigate to="/data/import" replace /> },
    { path: "/export", element: <Navigate to="/data/export" replace /> },
  ],
};
