// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import type { ReactNode } from "react";

/**
 * Announced status text for async outcomes (2026-08-19 review, A2).
 *
 * Every error in this app was previously a bare `<p className="form-error">`.
 * That renders fine visually, but a screen reader is never told about it:
 * the text appears in a region the user has already read past, with nothing
 * marking it as new. Submitting a bad login produced *no* announcement at
 * all — the failure was silent for anyone not looking at the screen.
 *
 * `role="alert"` (which implies aria-live="assertive") makes the assistive
 * technology interrupt and read the message when it appears. Reserved for
 * errors, where interrupting is warranted.
 *
 * `role="status"` (implying aria-live="polite") is the variant for success
 * and progress — it waits for a pause rather than cutting in, which is what
 * you want for "Saved" but not for "That didn't work".
 *
 * Note both roles must be present in the DOM *before* the text changes for
 * some screen readers to reliably announce it. Rendering the wrapper
 * unconditionally and leaving it empty is the robust pattern, which is why
 * this returns an empty live region rather than null when there's no
 * message — see `alwaysRendered`.
 */
export function StatusMessage({
  children,
  variant = "error",
  className,
  alwaysRendered = false,
  ...rest
}: {
  children?: ReactNode;
  variant?: "error" | "success";
  className?: string;
  alwaysRendered?: boolean;
} & Omit<React.HTMLAttributes<HTMLParagraphElement>, "children" | "className">) {
  const isError = variant === "error";
  const hasContent = children !== undefined && children !== null && children !== false;

  if (!hasContent && !alwaysRendered) return null;

  const classes = [isError ? "form-error" : "form-success", className].filter(Boolean).join(" ");

  return (
    <p
      className={classes}
      role={isError ? "alert" : "status"}
      // Assistive tech only announces changes inside a live region if it can
      // see the whole message; atomic re-reads the element rather than just
      // the changed text node.
      aria-atomic="true"
      {...rest}
    >
      {children}
    </p>
  );
}
