// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { forgetLegacyTokens, readLegacyRefreshToken, useAuthStore } from "../auth/authStore";

/**
 * Typed client for the connected web UI, calling the FastAPI backend
 * directly (JWT bearer auth, auto-refresh on 401). This deliberately does
 * NOT go through the Dexie/outbox/syncEngine scaffolding in ../db and
 * ../sync — that layer exists for the offline PWA path (Phase 4), which is
 * sequenced after the mobile sync protocol (Phase 2) is battle-tested. Until
 * then, the connected web UI reads/writes the backend directly, same as any
 * ordinary server-backed SPA — see docs/architecture.md Section 5.
 *
 * Session (Vikunja #93): the access token is held in memory only; the
 * refresh token is an HttpOnly cookie the server sets on /api/v1/auth/*,
 * which this code never sees. Every request carries SESSION_HEADER so the
 * server answers token-issuing calls in that cookie form.
 */
const API_BASE = "/api/v1";
const SESSION_HEADER = { "X-WrinkleByte-Session": "cookie" };

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function authHeaders(): HeadersInit {
  const { accessToken } = useAuthStore.getState();
  return accessToken ? { ...SESSION_HEADER, Authorization: `Bearer ${accessToken}` } : SESSION_HEADER;
}

let refreshInFlight: Promise<boolean> | null = null;

/**
 * Trade the refresh cookie for a new access token. Refresh tokens rotate,
 * and presenting one that was already rotated away revokes the whole login
 * (reuse detection), so two refreshes must never race with the same cookie.
 * Within this tab, concurrent callers share one request; across tabs, the
 * Web Locks API runs them one after another, and the second one simply
 * sends the cookie the first one just received.
 */
export function refreshAccessToken(): Promise<boolean> {
  refreshInFlight ??= withRefreshLock(doRefresh).finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

function withRefreshLock(fn: () => Promise<boolean>): Promise<boolean> {
  const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;
  return locks ? locks.request("wrinklebyte-auth-refresh", fn) : fn();
}

async function doRefresh(): Promise<boolean> {
  const { setAccessToken, clear } = useAuthStore.getState();
  // A session from before the cookie existed: send its token once, in
  // cookie mode, so the server answers with the cookie; then forget it.
  const legacy = readLegacyRefreshToken();
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "same-origin",
      headers: legacy ? { ...SESSION_HEADER, "Content-Type": "application/json" } : SESSION_HEADER,
      body: legacy ? JSON.stringify({ refresh_token: legacy }) : undefined,
    });
  } catch {
    // Offline or server unreachable: signed out for now; the cookie (or the
    // legacy token, kept until the server has answered) still works later.
    clear();
    return false;
  }
  if (legacy) forgetLegacyTokens();
  if (!response.ok) {
    clear();
    return false;
  }
  const body = (await response.json()) as { access_token: string };
  setAccessToken(body.access_token);
  return true;
}

/** On page load: turn the refresh cookie back into a session, if there is one. */
export async function restoreSession(): Promise<void> {
  if (!(await refreshAccessToken())) useAuthStore.getState().clear();
}

/** Log out on the server (revokes this login's refresh tokens and clears the
 * cookie), then locally. Local sign-out happens even if the server can't be
 * reached. */
export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE}/auth/logout`, { method: "POST", credentials: "same-origin", headers: SESSION_HEADER });
  } catch {
    // Signed out locally regardless; the cookie expires on its own.
  }
  forgetLegacyTokens();
  useAuthStore.getState().clear();
}

async function rawFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "same-origin",
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
