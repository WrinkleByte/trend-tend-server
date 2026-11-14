// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { NavLink } from "react-router-dom";

export interface TabItem {
  to: string;
  label: string;
  end?: boolean;
  badge?: number;
}

/** Tabs that are real addresses, so each one can be linked, bookmarked and
 * reached with the browser's back button. */
export function TabNav({ items, label }: { items: TabItem[]; label: string }) {
  return (
    <nav className="tab-nav" aria-label={label}>
      {items.map((item) => (
        <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => (isActive ? "active" : undefined)}>
          {item.label}
          {item.badge ? <span className="tab-badge">{item.badge}</span> : null}
        </NavLink>
      ))}
    </nav>
  );
}
