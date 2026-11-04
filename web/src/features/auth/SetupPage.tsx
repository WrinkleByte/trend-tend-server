// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { MIN_PASSWORD_LENGTH, PASSWORD_HINT, passwordPolicyError, register } from "../../api/auth";
import { ApiError } from "../../api/client";
import { useAuthStore } from "../../auth/authStore";
import { StatusMessage } from "../../components/StatusMessage";

/**
 * Shown instead of the normal login/register flow when GET /auth/setup-status
 * reports no user exists yet (see App.tsx's SetupGate) — the very first
 * account created this way becomes the instance admin (backend
 * app/api/v1/auth.py's register(), first-user rule) and can later configure
 * SMTP under Settings for password-reset emails.
 */
export function SetupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [householdName, setHouseholdName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const setTokens = useAuthStore((s) => s.setTokens);
  const navigate = useNavigate();

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const tokens = await register({
        email,
        password,
        display_name: displayName,
        household_name: householdName,
      });
      setTokens(tokens.access_token, tokens.refresh_token);
      navigate("/");
    } catch (err) {
      setError(
        passwordPolicyError(err) ??
          (err instanceof ApiError
            ? "Couldn't create the admin account — check your details and try again."
            : "Something went wrong."),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>Welcome to WrinkleByte Maintenance Tracker</h1>
        <p>This looks like a fresh install — set up the first account to get started.</p>
        {error && <StatusMessage>{error}</StatusMessage>}
        <label>
          Your name
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
        </label>
        <label>
          Household name
          <input
            placeholder="e.g. The Smith Family"
            value={householdName}
            onChange={(e) => setHouseholdName(e.target.value)}
            required
          />
        </label>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={MIN_PASSWORD_LENGTH}
            required
          />
          <small className="field-hint">{PASSWORD_HINT}</small>
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? "Setting up…" : "Create admin account"}
        </button>
        <p>You can configure email (for password resets) later under Settings.</p>
      </form>
    </div>
  );
}
