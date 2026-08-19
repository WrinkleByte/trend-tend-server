import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { resetPassword } from "../../api/auth";
import { ApiError } from "../../api/client";
import { StatusMessage } from "../../components/StatusMessage";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => resetPassword(token!, password),
    onSuccess: () => navigate("/login"),
    onError: (err) =>
      setError(
        err instanceof ApiError && err.status === 400
          ? "This reset link is invalid or has expired — request a new one."
          : "Something went wrong.",
      ),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    mutation.mutate();
  }

  if (!token) {
    return (
      <div className="auth-page">
        <div className="auth-form">
          <h1>Reset password</h1>
          <p>This link is missing a reset token.</p>
          <p>
            <Link to="/forgot-password">Request a new link</Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>Choose a new password</h1>
        {error && (
          <StatusMessage>
            {error} <Link to="/forgot-password">Request a new link</Link>
          </StatusMessage>
        )}
        <label>
          New password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
        </label>
        <button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Saving…" : "Reset password"}
        </button>
      </form>
    </div>
  );
}
