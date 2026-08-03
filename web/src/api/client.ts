/**
 * Hand-written placeholder for the typed API client. Once the backend is
 * running, replace this with a generated client via openapi-typescript
 * against the FastAPI backend's /openapi.json — see docs/architecture.md
 * Section 5. Kept minimal here since Phase 0/4 scope is scaffolding, not the
 * full connected-CRUD implementation.
 */
const API_BASE = "/api/v1";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}
