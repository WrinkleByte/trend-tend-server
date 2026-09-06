import { ApiError, apiFetch } from "./client";
import type { TokenResponse } from "./types";

// Mirrors MIN_PASSWORD_LENGTH in the backend's app/schemas/auth.py. The two
// silently drifted once: the backend raised its minimum from 8 to 12 in the
// 2026-08-19 password-policy review, every password form here stayed at 8, and
// a 12-character-shy password sailed past browser validation only to come back
// as an opaque 422 the forms rendered as "Something went wrong." Keep in step.
export const MIN_PASSWORD_LENGTH = 12;

export const PASSWORD_HINT = `At least ${MIN_PASSWORD_LENGTH} characters.`;

/**
 * Turns the backend's password-policy rejection into something a person can
 * act on, or null when the error is about anything else (so callers can fall
 * through to their own handling).
 *
 * A 422 body is Pydantic's error array, which is not showable as-is — hence
 * matching on it here rather than surfacing err.message. The `password` check
 * keeps this from mislabelling a 422 raised over some other field.
 */
export function passwordPolicyError(err: unknown): string | null {
  if (err instanceof ApiError && err.status === 422 && err.message.includes('"password"')) {
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
  }
  return null;
}

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
  // Whether an instance admin has left self-service signup open. Purely a
  // rendering hint — the backend enforces it in register() regardless, so a
  // client that ignores this still can't create an account.
  allow_self_registration: boolean;
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
