import { apiFetch } from "./client";

export interface AdminHouseholdMember {
  user_id: string;
  email: string;
  display_name: string;
  role: "owner" | "member";
  is_instance_admin: boolean;
  joined_at: string;
}

export interface AdminHouseholdRecordCounts {
  assets: number;
  fuel_logs: number;
  trip_logs: number;
  maintenance_records: number;
  maintenance_schedules: number;
}

export interface AdminHouseholdSummary {
  id: string;
  name: string;
  created_at: string;
  members: AdminHouseholdMember[];
  record_counts: AdminHouseholdRecordCounts;
}

export interface PromoteUserResponse {
  id: string;
  email: string;
  is_instance_admin: boolean;
}

export function listAllHouseholds(): Promise<AdminHouseholdSummary[]> {
  return apiFetch("/admin/households");
}

export function promoteUserToInstanceAdmin(userId: string): Promise<PromoteUserResponse> {
  return apiFetch(`/admin/users/${userId}/promote`, { method: "POST" });
}

export function demoteUserFromInstanceAdmin(userId: string): Promise<PromoteUserResponse> {
  return apiFetch(`/admin/users/${userId}/demote`, { method: "POST" });
}

export function deleteHouseholdAsAdmin(householdId: string): Promise<void> {
  return apiFetch(`/admin/households/${householdId}`, { method: "DELETE" });
}
