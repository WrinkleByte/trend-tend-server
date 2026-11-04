// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useState, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { MIN_PASSWORD_LENGTH, PASSWORD_HINT, passwordPolicyError, register } from "../../api/auth";
import { ApiError } from "../../api/client";
import { acceptInvite, previewInvite } from "../../api/households";
import { isAuthenticated, useAuthStore } from "../../auth/authStore";
import { StatusMessage } from "../../components/StatusMessage";

const STATUS_MESSAGES: Record<string, string> = {
  accepted: "This invite has already been used.",
  revoked: "This invite has been revoked.",
  expired: "This invite has expired.",
};

export function JoinPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const navigate = useNavigate();
  const setTokens = useAuthStore((s) => s.setTokens);

  const {
    data: preview,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["invite-preview", token],
    queryFn: () => previewInvite(token!),
    enabled: !!token,
    retry: false,
  });

  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const acceptMutation = useMutation({
    mutationFn: () => acceptInvite(token!),
    onSuccess: (tokens) => {
      setTokens(tokens.access_token, tokens.refresh_token);
      navigate("/");
    },
    onError: () => setError("Couldn't accept this invite — it may no longer be valid."),
  });

  const registerMutation = useMutation({
    mutationFn: () =>
      register({ email: preview!.invited_email, password, display_name: displayName, invite_token: token! }),
    onSuccess: (tokens) => {
      setTokens(tokens.access_token, tokens.refresh_token);
      navigate("/");
    },
    onError: (err) =>
      setError(
        passwordPolicyError(err) ??
          (err instanceof ApiError && err.status === 409
            ? "That email is already registered — log in instead."
            : "Something went wrong."),
      ),
  });

  function handleRegisterSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    registerMutation.mutate();
  }

  if (!token) {
    return (
      <div className="auth-page">
        <p>This link is missing an invite token.</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="auth-page">
        <p>Loading invite…</p>
      </div>
    );
  }

  if (isError || !preview) {
    return (
      <div className="auth-page">
        <p>This invite link isn&rsquo;t valid.</p>
      </div>
    );
  }

  if (preview.status !== "pending") {
    return (
      <div className="auth-page">
        <p>{STATUS_MESSAGES[preview.status] ?? "This invite is no longer valid."}</p>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-form">
        <h1>Join {preview.household_name}</h1>
        <p>
          You&rsquo;ve been invited to join as a <strong>{preview.role}</strong>, using{" "}
          <strong>{preview.invited_email}</strong>.
        </p>
        {error && <StatusMessage>{error}</StatusMessage>}

        {isAuthenticated() ? (
          <button type="button" disabled={acceptMutation.isPending} onClick={() => acceptMutation.mutate()}>
            Accept invite
          </button>
        ) : (
          <form onSubmit={handleRegisterSubmit}>
            <label>
              Your name
              <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
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
            <button type="submit" disabled={registerMutation.isPending}>
              Create account &amp; join
            </button>
            <p>
              Already have an account?{" "}
              <Link to={`/login?next=${encodeURIComponent(`/join?token=${token}`)}`}>Log in</Link>, then this page
              will let you accept the invite.
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
