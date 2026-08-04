import { apiFetch } from "./client";
import type { TokenResponse } from "./types";

export interface RegisterInput {
  email: string;
  password: string;
  display_name: string;
  household_name: string;
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
