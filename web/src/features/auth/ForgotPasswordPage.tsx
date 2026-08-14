import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { forgotPassword } from "../../api/auth";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");

  // Always succeeds from the UI's perspective — the backend intentionally
  // returns the same 200 response whether or not the email is registered,
  // so it can't be used to enumerate accounts. See app/api/v1/auth.py's
  // forgot_password().
  const mutation = useMutation({ mutationFn: () => forgotPassword(email) });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  if (mutation.isSuccess) {
    return (
      <div className="auth-page">
        <div className="auth-form">
          <h1>Check your email</h1>
          <p>If that email is registered, we&rsquo;ve sent a link to reset your password.</p>
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
        <h1>Forgot password</h1>
        <p>Enter your email and we&rsquo;ll send you a reset link, if email is configured on this instance.</p>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Sending…" : "Send reset link"}
        </button>
        <p>
          <Link to="/login">Back to log in</Link>
        </p>
      </form>
    </div>
  );
}
