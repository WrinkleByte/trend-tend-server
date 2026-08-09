import { apiFetch } from "./client";
import type { TokenResponse } from "./types";

export interface RegisterInput {
  email: string;
  password: string;
  display_name: string;
  // Exactly one of these is required — household_name creates a new
  // household (normal signup), invite_token joins an existing one instead.
  household_name?: string;
  invite_token?: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

export function register(input: RegisterInput): Promise<TokenResponse> {
  return apiFetch("/auth/register", { method: "POST", body: JSON.stringify(input) });
}

export function login(input: LoginInput): Promise<TokenResponse> {
  return apiFetch("/auth/login", { method: "POST", body: JSON.stringify(input) });
}

export interface SetupStatus {
  setup_complete: boolean;
}

// Unauthenticated by design — see backend app/api/v1/auth.py's
// setup_status(). A freshly-deployed instance has no user yet, so nothing
// could call this with credentials.
export function getSetupStatus(): Promise<SetupStatus> {
  return apiFetch("/auth/setup-status");
}

export function forgotPassword(email: string): Promise<{ detail: string }> {
  return apiFetch("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) });
}

export function resetPassword(token: string, newPassword: string): Promise<{ detail: string }> {
  return apiFetch("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}
