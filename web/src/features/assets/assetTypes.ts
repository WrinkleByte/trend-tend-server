// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import type { AssetType } from "../../api/types";

export const ASSET_TYPES: { value: AssetType; label: string }[] = [
  { value: "vehicle", label: "Vehicle" },
  { value: "equipment", label: "Equipment" },
  { value: "property", label: "Property" },
  { value: "home_system", label: "Home System" },
  { value: "valuable", label: "Valuable" },
];
