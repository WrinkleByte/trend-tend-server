import { apiFetch } from "./client";
import type { ApiTokenCreated, ApiTokenSummary } from "./types";

export function listApiTokens(): Promise<ApiTokenSummary[]> {
  return apiFetch("/api-tokens");
}

export function createApiToken(name: string): Promise<ApiTokenCreated> {
  return apiFetch("/api-tokens", { method: "POST", body: JSON.stringify({ name }) });
}

export function revokeApiToken(id: string): Promise<void> {
  return apiFetch(`/api-tokens/${id}`, { method: "DELETE" });
}

// Only valid once a token is already revoked (backend enforces revoke-first,
// see api_tokens.py's delete_api_token doc comment) -- removes the row
// entirely rather than just marking it inactive.
export function deleteApiToken(id: string): Promise<void> {
  return apiFetch(`/api-tokens/${id}/permanently`, { method: "DELETE" });
}
