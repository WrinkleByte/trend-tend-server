// Mirrors the FastAPI Pydantic response schemas field-for-field (snake_case,
// as sent over the wire) — see backend/app/schemas/*.py. Deliberately
// hand-written rather than generated for now; see ../../README.md.

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export type AssetType = "vehicle" | "equipment" | "property" | "home_system";
export type AssetStatus = "active" | "archived" | "disposed";

export interface VehicleDetails {
  vin: string | null;
  make: string | null;
  model: string | null;
  year: number | null;
  license_plate: string | null;
  current_mileage: number | null;
  mileage_unit: string;
  fuel_type: string | null;
}

export interface EquipmentDetails {
  manufacturer: string | null;
  model_number: string | null;
  serial_number: string | null;
  warranty_expiration: string | null;
}

export interface PropertyDetails {
  address: string | null;
  parent_asset_id: string | null;
  install_date: string | null;
}

export interface Asset {
  id: string;
  household_id: string;
  asset_type: AssetType;
  name: string;
  notes: string | null;
  status: AssetStatus;
  purchase_date: string | null;
  purchase_cost: number | null;
  // Set via POST /attachments?asset_id=..., cleared via
  // DELETE /assets/{id}/photo — not part of AssetCreateInput, same
  // reasoning as the backend's AssetCreate/AssetUpdate schemas.
  photo_attachment_id: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  vehicle_details: VehicleDetails | null;
  equipment_details: EquipmentDetails | null;
  property_details: PropertyDetails | null;
}

export interface AssetCreateInput {
  asset_type: AssetType;
  name: string;
  notes?: string | null;
  // Update-only — a new asset always starts "active" (the backend model's
  // default), never sent on create; present here so `Partial<AssetCreateInput>`
  // stays the one type `updateAsset` needs, matching backend AssetUpdate.
  status?: AssetStatus;
  purchase_date?: string | null;
  purchase_cost?: number | null;
  vehicle_details?: Partial<VehicleDetails> | null;
  equipment_details?: Partial<EquipmentDetails> | null;
  property_details?: Partial<PropertyDetails> | null;
}

export interface MaintenanceRecord {
  id: string;
  household_id: string;
  asset_id: string;
  performed_at: string;
  performed_by: string | null;
  category: string;
  custom_category: string | null;
  additional_categories: string | null;
  description: string | null;
  cost: string | null;
  currency: string;
  odometer_reading: number | null;
  schedule_id: string | null;
  oil_viscosity: string | null;
  oil_formulation: string | null;
  oil_meets_dexos: boolean | null;
  filter_part_number: string | null;
  fluid_type: string | null;
  capacity: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface MaintenanceRecordCreateInput {
  asset_id: string;
  performed_at: string;
  performed_by?: string | null;
  category: string;
  custom_category?: string | null;
  additional_categories?: string | null;
  description?: string | null;
  cost?: number | null;
  currency?: string;
  odometer_reading?: number | null;
  schedule_id?: string | null;
  oil_viscosity?: string | null;
  oil_formulation?: string | null;
  oil_meets_dexos?: boolean | null;
  filter_part_number?: string | null;
  fluid_type?: string | null;
  capacity?: string | null;
}

export type IntervalType = "time" | "usage" | "both";

export interface MaintenanceSchedule {
  id: string;
  household_id: string;
  asset_id: string;
  name: string;
  interval_type: IntervalType;
  interval_days: number | null;
  interval_usage_amount: number | null;
  usage_field: string | null;
  anchor_date: string | null;
  anchor_usage_value: number | null;
  active: boolean;
  dismissed_at: string | null;
  next_due_date: string | null;
  next_due_usage: number | null;
  is_overdue: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface MaintenanceScheduleCreateInput {
  asset_id: string;
  name: string;
  interval_type: IntervalType;
  interval_days?: number | null;
  interval_usage_amount?: number | null;
  usage_field?: string | null;
  anchor_date?: string | null;
  anchor_usage_value?: number | null;
}

export interface MaintenanceScheduleUpdateInput {
  name?: string;
  interval_days?: number | null;
  interval_usage_amount?: number | null;
  anchor_date?: string | null;
  anchor_usage_value?: number | null;
  active?: boolean | null;
  dismissed_at?: string | null;
}

export type StorageBackendType = "local_disk" | "s3";

export interface Attachment {
  id: string;
  household_id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  storage_backend: StorageBackendType;
  sha256: string;
  thumbnail_storage_key: string | null;
  captured_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  url: string;
}

export interface ApiTokenSummary {
  id: string;
  name: string;
  scopes: Record<string, unknown>;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
}

export interface ApiTokenCreated extends ApiTokenSummary {
  token: string;
}

export type HouseholdRole = "owner" | "member";
export type InviteStatus = "pending" | "accepted" | "revoked" | "expired";

export interface Household {
  id: string;
  name: string;
  owner_user_id: string;
  settings: Record<string, unknown>;
  created_at: string;
  my_role: HouseholdRole;
}

export interface HouseholdMember {
  user_id: string;
  email: string;
  display_name: string;
  role: HouseholdRole;
  joined_at: string;
}

export interface HouseholdInvite {
  id: string;
  invited_email: string;
  role: HouseholdRole;
  status: InviteStatus;
  token: string;
  created_at: string;
  expires_at: string;
}

export interface InvitePreview {
  household_name: string;
  invited_email: string;
  role: HouseholdRole;
  status: InviteStatus;
  expires_at: string;
}

// Fuel Logs
export interface FuelLog {
  id: string;
  household_id: string;
  asset_id: string;
  performed_at: string;
  odometer_reading: number | null;
  gallons: string;
  cost_per_gallon: string | null;
  total_cost: string | null;
  currency: string;
  is_fill_up: boolean;
  mpg: string | null;
  octane: number | null;
  cetane: number | null;
  gas_brand: string | null;
  location: string | null;
  notes: string | null;
  additive: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface CreateFuelLogRequest {
  asset_id: string;
  performed_at: string;
  odometer_reading?: number | null;
  gallons: string;
  cost_per_gallon?: string | null;
  total_cost?: string | null;
  currency?: string;
  is_fill_up?: boolean;
  mpg?: string | null;
  octane?: number | null;
  cetane?: number | null;
  gas_brand?: string | null;
  location?: string | null;
  notes?: string | null;
  additive?: string | null;
}

// Trip Logs
// purpose is a fixed set (business/personal/medical/charity/commute/other)
// plus free text, same pattern as maintenance record category/custom_category
// — see shared/src/commonMain/kotlin/com/wrinklebyte/domain/TripLogInput.kt
// in tendfida-mobile for where that set is defined.
export type TripPurpose = "business" | "personal" | "medical" | "charity" | "commute" | "other";

export interface TripLog {
  id: string;
  household_id: string;
  asset_id: string;
  performed_at: string;
  purpose: TripPurpose;
  custom_purpose: string | null;
  start_odometer: string | null;
  end_odometer: string;
  distance: string;
  notes: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface CreateTripLogRequest {
  asset_id: string;
  performed_at: string;
  purpose: TripPurpose;
  custom_purpose?: string | null;
  start_odometer?: string | null;
  end_odometer: string;
  distance: string;
  notes?: string | null;
}
