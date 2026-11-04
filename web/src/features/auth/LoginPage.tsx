// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { login } from "../../api/auth";
import { ApiError } from "../../api/client";
import { useAuthStore } from "../../auth/authStore";
import { StatusMessage } from "../../components/StatusMessage";
import { useSetupStatus } from "./useSetupStatus";
import { LegalNotice } from "../../components/LegalNotice";

export function LoginPage() {
  const { data: setupStatus } = useSetupStatus();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const setTokens = useAuthStore((s) => s.setTokens);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const next = searchParams.get("next") || "/";

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const tokens = await login({ email, password });
      setTokens(tokens.access_token, tokens.refresh_token);
      navigate(next);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? "Invalid email or password." : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>Log in</h1>
        {error && <StatusMessage>{error}</StatusMessage>}
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? "Logging in…" : "Log in"}
        </button>
        <p>
          <Link to="/forgot-password">Forgot password?</Link>
        </p>
        {/* Hidden rather than disabled when signups are closed: there is no
            self-service route to offer, and an invited user reaches /join
            directly from their invite link, never through here. Defaults to
            shown while the status is still loading so the link doesn't
            flicker in on an ordinary open instance. */}
        {setupStatus?.allow_self_registration !== false && (
          <p>
            No account? <Link to="/register">Register</Link>
          </p>
        )}
      </form>
      <LegalNotice />
    </div>
  );
}
