import type { AssetType } from "../../api/types";

export const ASSET_TYPES: { value: AssetType; label: string }[] = [
  { value: "vehicle", label: "Vehicle" },
  { value: "equipment", label: "Equipment" },
  { value: "property", label: "Property" },
  { value: "home_system", label: "Home System" },
];
