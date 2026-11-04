// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useAuthStore } from "../auth/authStore";

/**
 * Typed client for the connected web UI, calling the FastAPI backend
 * directly (JWT bearer auth, auto-refresh on 401). This deliberately does
 * NOT go through the Dexie/outbox/syncEngine scaffolding in ../db and
 * ../sync — that layer exists for the offline PWA path (Phase 4), which is
 * sequenced after the mobile sync protocol (Phase 2) is battle-tested. Until
 * then, the connected web UI reads/writes the backend directly, same as any
 * ordinary server-backed SPA — see docs/architecture.md Section 5.
 */
const API_BASE = "/api/v1";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function authHeaders(): HeadersInit {
  const { accessToken } = useAuthStore.getState();
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
}

async function refreshAccessToken(): Promise<boolean> {
  const { refreshToken, setTokens, clear } = useAuthStore.getState();
  if (!refreshToken) return false;
  const response = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    clear();
    return false;
  }
  const body = (await response.json()) as { access_token: string; refresh_token: string };
  setTokens(body.access_token, body.refresh_token);
  return true;
}

async function rawFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...init?.headers },
  });
}

async function withRetryOn401(path: string, init?: RequestInit): Promise<Response> {
  let response = await rawFetch(path, init);
  if (response.status === 401 && (await refreshAccessToken())) {
    response = await rawFetch(path, init);
  }
  return response;
}

async function unwrap(response: Response): Promise<void> {
  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(response.status, detail || response.statusText);
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await withRetryOn401(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  await unwrap(response);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  // No Content-Type here — the browser sets the multipart boundary itself.
  const response = await withRetryOn401(path, { method: "POST", body: formData });
  await unwrap(response);
  return response.json() as Promise<T>;
}

export async function apiFetchBlob(path: string): Promise<Blob> {
  const response = await withRetryOn401(path);
  await unwrap(response);
  return response.blob();
}
