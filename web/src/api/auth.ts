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
