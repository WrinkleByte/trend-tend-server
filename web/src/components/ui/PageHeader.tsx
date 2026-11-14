// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import type { ReactNode } from "react";
import { Link } from "react-router-dom";

/** The title block every page starts with. `back` adds a one-level trail
 * ("Assets / Outback") so a detail page always has a visible way out. */
export function PageHeader({
  title,
  subtitle,
  back,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  back?: { to: string; label: string };
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {back && (
          <nav className="page-trail" aria-label="Breadcrumb">
            <Link to={back.to}>{back.label}</Link>
            <span aria-hidden="true">/</span>
          </nav>
        )}
        <h1>{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}
