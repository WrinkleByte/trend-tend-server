// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useId } from "react";
import { GridField } from "../../components/GridField";
import type { ServiceDefaults } from "../../api/types";

/** Service Defaults on the asset's Details tab, next to the other detail fields
 * and committed by the same Save button.
 *
 * They used to live inside `vehicle_details` and moved to their own
 * `service_defaults` table (backend card #824) precisely so equipment and
 * property can remember specs too, so this section is NOT gated on the asset
 * being a vehicle — only `valuable` gets nothing, because its categories
 * (repair, replacement, appraisal) are not spec-driven and the backend gives
 * those assets no row.
 *
 * The caller seeds this from the asset's stored values (see AssetDetailPage's
 * form initialization). That matters: the server treats an absent key as "leave
 * it alone" and a null as "clear it", so a form that started blank would erase
 * everything on the first Save. Here a field shows what is stored, and blanking
 * it is a deliberate clear.
 */

type FieldKey = keyof ServiceDefaults;
type Patch = Partial<ServiceDefaults>;

type Field = { key: FieldKey; label: string; placeholder?: string };

const OIL_AND_FILTERS: Field[] = [
  { key: "default_oil_viscosity", label: "Oil viscosity", placeholder: "e.g. 5W-30" },
  { key: "default_oil_formulation", label: "Oil formulation", placeholder: "e.g. Full Synthetic" },
  { key: "default_oil_capacity", label: "Oil capacity", placeholder: "e.g. 6 qt" },
  { key: "default_motor_oil_brand", label: "Motor oil brand", placeholder: "e.g. Shell, Pennzoil, Mopar" },
  { key: "default_oil_filter_part_number", label: "Oil filter part", placeholder: "e.g. 3600" },
  { key: "default_oil_filter_brand", label: "Oil filter brand", placeholder: "e.g. Fram, K&N" },
  { key: "default_air_filter_part_number", label: "Air filter part", placeholder: "e.g. TA1093" },
  { key: "default_air_filter_brand", label: "Air filter brand", placeholder: "e.g. K&N" },
  { key: "default_fuel_filter_part_number", label: "Fuel filter part", placeholder: "e.g. 2R-2451" },
  { key: "default_fuel_filter_brand", label: "Fuel filter brand", placeholder: "e.g. Kohler" },
];

const EQUIPMENT_FLUIDS: Field[] = [
  { key: "default_hydraulic_fluid_type", label: "Hydraulic fluid", placeholder: "e.g. AW32" },
  { key: "default_hydraulic_fluid_capacity", label: "Hydraulic capacity", placeholder: "e.g. 12 qt" },
];

const HOME_FILTERS: Field[] = [
  { key: "default_hvac_filter_size", label: "HVAC filter size", placeholder: "e.g. 20x25x1" },
  { key: "default_hvac_filter_brand", label: "HVAC filter brand", placeholder: "e.g. FilterBuy" },
  { key: "default_water_filter_cartridge", label: "Water filter cartridge", placeholder: "e.g. RPWL203U" },
  { key: "default_water_filter_brand", label: "Water filter brand", placeholder: "e.g. GE" },
];

const VEHICLE_DRIVETRAIN: Field[] = [
  { key: "default_transmission_fluid_type", label: "Transmission fluid", placeholder: "e.g. ATF+4" },
  { key: "default_transmission_filter_part_number", label: "Transmission filter part" },
  { key: "default_transmission_fluid_capacity", label: "Transmission capacity", placeholder: "e.g. 12 qt" },
  { key: "default_coolant_type", label: "Coolant type", placeholder: "e.g. OAT" },
  { key: "default_differential_front_fluid_type", label: "Front differential fluid", placeholder: "e.g. 75W-90" },
  { key: "default_differential_front_capacity", label: "Front differential capacity" },
  { key: "default_differential_rear_fluid_type", label: "Rear differential fluid", placeholder: "e.g. 75W-90" },
  { key: "default_differential_rear_capacity", label: "Rear differential capacity" },
];

/** One wire schema for every serviced type; which subset a screen offers is the
 * per-type decision (the backend says the same in ServiceDefaultsIn). */
function groupsFor(assetType: string): { title: string; fields: Field[] }[] {
  if (assetType === "vehicle")
    return [{ title: "Oil and filters", fields: OIL_AND_FILTERS }, { title: "Drivetrain and coolants", fields: VEHICLE_DRIVETRAIN }];
  if (assetType === "equipment")
    return [{ title: "Oil and filters", fields: OIL_AND_FILTERS }, { title: "Other fluids", fields: EQUIPMENT_FLUIDS }];
  if (assetType === "property" || assetType === "home_system") return [{ title: "Home filters", fields: HOME_FILTERS }];
  return [];
}

/** dexos is a yes/no/not-asked, not a text box: "No" is a real answer about a
 * diesel spec and an empty text field cannot tell those apart. */
function DexosField({
  value,
  onChange,
}: {
  value: ServiceDefaults["default_oil_meets_dexos"] | undefined;
  onChange: (p: Patch) => void;
}) {
  const id = useId();
  const current = value == null ? "" : value ? "yes" : "no";
  return (
    <div className="field-full">
      <label htmlFor={id}>Oil meets dexos</label>
      <select
        id={id}
        value={current}
        onChange={(e) => onChange({ default_oil_meets_dexos: e.target.value === "" ? null : e.target.value === "yes" })}
      >
        <option value="">Not set</option>
        <option value="yes">Yes</option>
        <option value="no">No</option>
      </select>
    </div>
  );
}

export function ServiceDefaultsFields({
  assetType,
  value,
  onChange,
}: {
  assetType: string;
  // null is a real shape here: an asset with no service_defaults row at all.
  value: Patch | null | undefined;
  onChange: (patch: Patch) => void;
}) {
  const groups = groupsFor(assetType);
  if (groups.length === 0) return null;

  const stored = groups
    .flatMap((g) => g.fields.map((f) => value?.[f.key]))
    .filter((v) => v != null && v !== false && v !== "").length;

  return (
    <>
      <h2 style={{ marginTop: 24 }}>Service Defaults</h2>
      <p className="field-hint">
        {stored > 0
          ? `${stored} remembered ${stored === 1 ? "spec" : "specs"} — prefilled into new maintenance records and used to build shopping links. Clear a box to unset it.`
          : "Nothing remembered for this asset yet. Fill these in and new maintenance records start prefilled."}
      </p>
      {groups.map((group) => (
        <div key={group.title}>
          <h3 style={{ marginTop: 12 }}>{group.title}</h3>
          <div className="field-grid field-compact">
            {group.fields.map((field) =>
              field.key === "default_oil_meets_dexos" ? (
                <DexosField
                  key={field.key}
                  value={value?.default_oil_meets_dexos}
                  onChange={onChange}
                />
              ) : (
                <GridField
                  key={field.key}
                  label={field.label}
                  placeholder={field.placeholder}
                  value={typeof value?.[field.key] === "string" ? (value[field.key] as string) : ""}
                  onChange={(v) => onChange({ [field.key]: v.trim() || null } as Patch)}
                />
              ),
            )}
          </div>
        </div>
      ))}
    </>
  );
}
