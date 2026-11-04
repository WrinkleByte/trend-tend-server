// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { MIN_PASSWORD_LENGTH, PASSWORD_HINT, passwordPolicyError, register } from "../../api/auth";
import { ApiError } from "../../api/client";
import { useAuthStore } from "../../auth/authStore";
import { StatusMessage } from "../../components/StatusMessage";
import { useSetupStatus } from "./useSetupStatus";

export function RegisterPage() {
  const { data: setupStatus } = useSetupStatus();
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
          (err instanceof ApiError && err.status === 409
            ? "That email is already registered."
            : err instanceof ApiError && err.status === 403
              ? "This instance isn't accepting new signups. Ask a household owner to invite you."
              : "Something went wrong."),
      );
    } finally {
      setSubmitting(false);
    }
  }

  // Someone can still reach /register by typing the URL after an admin closed
  // signups. Say so plainly instead of showing a form whose only possible
  // outcome is a 403.
  if (setupStatus && !setupStatus.allow_self_registration) {
    return (
      <div className="auth-page">
        <div className="auth-form">
          <h1>Registration is closed</h1>
          <p>
            This instance isn&rsquo;t accepting new signups. If someone has invited you to their
            household, open the invite link they sent you.
          </p>
          <p>
            <Link to="/login">Back to log in</Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>Create your household</h1>
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
          {submitting ? "Creating…" : "Create account"}
        </button>
        <p>
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  );
}
