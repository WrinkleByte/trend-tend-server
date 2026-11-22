# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""Service Defaults — the asset-level home for remembered service specs, and the
single place that knows how the old vehicle-only wire fields relate to it.

Two things are true at once, and this module exists so they stay true:

1. **The field names never changed.** `vehicle_details.default_oil_filter_part_number`
   became `service_defaults.default_oil_filter_part_number`. A client that still sends
   `vehicle_details.default_oil_filter_part_number` and a client that sends
   `service_defaults.default_oil_filter_part_number` mean the identical thing. That is
   deliberate: it is what lets an app shipped in 2025 and an app shipped next month write
   the same value, so the storage move needs no coordinated client release.

2. **Nothing may be lost in the move.** Both halves of the compatibility path are
   therefore required, not optional:
   - *Write:* a payload carrying the legacy fields must land in `service_defaults`. If
     the server simply stopped declaring those fields, Pydantic would drop the unknown
     keys silently and a shipping app's saved specs would quietly stop persisting — the
     user would see their defaults vanish on the next device, with no error anywhere.
   - *Read:* a vehicle response must still carry the legacy fields inside
     `vehicle_details`. Those clients read them there; serving them only under the new
     key reads to them as "this vehicle has no saved specs".

Writes are **key-presence aware** (`model_fields_set`), the same rule `sale_price` and
`sale_date` use in sync.py: a client that does not send a field must not clear it. Without
this, an older app that knows nine of the twenty-three fields would blank the other
fourteen every time the user edited the asset's name.
"""

from typing import Any

# The fourteen specs that moved out of vehicle_details (see alembic
# d7c2f4a1b8e3). Order matches the migration's _RELOCATED list; the identity
# mapping is the point, so it is written as one list rather than a dict.
LEGACY_VEHICLE_DEFAULT_FIELDS: tuple[str, ...] = (
    "default_oil_viscosity",
    "default_oil_formulation",
    "default_oil_meets_dexos",
    "default_oil_filter_part_number",
    "default_air_filter_part_number",
    "default_transmission_fluid_type",
    "default_coolant_type",
    "default_differential_front_fluid_type",
    "default_differential_rear_fluid_type",
    "default_oil_capacity",
    "default_transmission_filter_part_number",
    "default_transmission_fluid_capacity",
    "default_differential_front_capacity",
    "default_differential_rear_capacity",
)

# Fields only the newer clients send: the three brands the mobile app already
# collects (its 21.sqm shipped them with no server-side counterpart, so every
# saved brand has been dropped on the way to the server until now), plus the
# equipment and property specs those asset types' category lists already offer.
NEW_DEFAULT_FIELDS: tuple[str, ...] = (
    "default_motor_oil_brand",
    "default_oil_filter_brand",
    "default_air_filter_brand",
    "default_fuel_filter_part_number",
    "default_fuel_filter_brand",
    "default_hydraulic_fluid_type",
    "default_hydraulic_fluid_capacity",
    "default_hvac_filter_size",
    "default_hvac_filter_brand",
    "default_water_filter_cartridge",
    "default_water_filter_brand",
)

SERVICE_DEFAULT_FIELDS: tuple[str, ...] = LEGACY_VEHICLE_DEFAULT_FIELDS + NEW_DEFAULT_FIELDS


def _sent_fields(payload: Any) -> set[str]:
    """Keys the client actually put in the payload.

    Pydantic fills absent optional fields with None, and `model_dump()` then reports
    every field as present-and-null — which is exactly the shape that would turn "this
    client has never heard of hydraulic fluid" into "clear this asset's hydraulic fluid".
    """
    return set(getattr(payload, "model_fields_set", set()) or set())


def defaults_from_payload(
    service_defaults: Any,
    legacy_vehicle_details: Any,
) -> dict[str, Any] | None:
    """Columns to write into service_defaults, from either payload shape.

    The new key wins when a client sends both (a client that has learned the new shape is
    the authority on it). Legacy keys are applied only for the fields that client actually
    sent. Returns None when the payload carried no service-default intent at all, which
    callers treat as "leave the stored row alone" — the same no-wipe rule
    _upsert_asset_details already applies to the detail tables.
    """
    out: dict[str, Any] = {}

    if service_defaults is not None:
        for field in _sent_fields(service_defaults) & set(SERVICE_DEFAULT_FIELDS):
            out[field] = getattr(service_defaults, field)

    if legacy_vehicle_details is not None:
        legacy_sent = _sent_fields(legacy_vehicle_details) & set(LEGACY_VEHICLE_DEFAULT_FIELDS)
        for field in legacy_sent:
            # Only fill what the new payload left open, so a client that sends both
            # shapes cannot have the stale copy overwrite the fresh one.
            out.setdefault(field, getattr(legacy_vehicle_details, field))

    return out or None


def legacy_defaults_for_response(row: Any) -> dict[str, Any]:
    """The vehicle_details-side view of a service_defaults row.
    Outbound compatibility: the fields a pre-move client reads out of
    `vehicle_details`, rebuilt from the row that now lives in service_defaults. Reads are
    unconditional (not key-presence based) — a client that always sends all fourteen
    expects all fourteen back, including the nulls, or it cannot tell "cleared" from
    "never sent".
    """
    if row is None:
        return {}
    return {field: getattr(row, field, None) for field in LEGACY_VEHICLE_DEFAULT_FIELDS}


def vehicle_columns(payload: Any) -> dict[str, Any]:
    """The fields of a vehicle detail payload that are actually VehicleDetails columns.

    Required, not tidy: the wire schemas still declare the fourteen legacy specs (so old
    clients keep sending and reading them) while the table no longer has those columns.
    Constructing `VehicleDetails(**payload.model_dump())` would therefore raise TypeError
    on every asset save, and the fourteen values are already being written to
    service_defaults by defaults_from_payload above -- here they are simply not passed on.
    """
    return {k: v for k, v in payload.model_dump().items() if k not in LEGACY_VEHICLE_DEFAULT_FIELDS}
