// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { getCurrentHousehold } from "../../api/households";
import { FEATURES } from "../../app/features";
import type { NavEntry } from "../../app/featureTypes";
import { logout } from "../../api/client";
import { LegalNotice } from "../../components/LegalNotice";
import { Icon } from "../../components/ui/Icon";

const NAV: NavEntry[] = FEATURES.flatMap((feature) => (feature.nav ? [feature.nav] : []));
const PRIMARY = NAV.filter((entry) => entry.placement === "primary");
const ACCOUNT = NAV.filter((entry) => entry.placement === "account");

function NavItem({ entry }: { entry: NavEntry }) {
  const { pathname } = useLocation();
  const alsoActive = entry.alsoActiveUnder != null && pathname.startsWith(entry.alsoActiveUnder);
  return (
    <NavLink
      to={entry.to}
      end={entry.end}
      className={({ isActive }) => (isActive || alsoActive ? "active" : undefined)}
    >
      <Icon name={entry.icon} />
      <span>{entry.label}</span>
    </NavLink>
  );
}

/** The signed-in app shell. Desktop: a fixed sidebar with the everyday pages
 * at the top and the occasional ones (import/export, settings, log out) at
 * the bottom. Phone: a slim top bar plus a bottom tab bar within thumb
 * reach, whose "More" tab opens a sheet with the occasional ones. Both are
 * built from the feature registry, so a new feature shows up in each
 * without touching this file. Which of the two is visible is decided purely
 * by shell.css's breakpoint. */
export function Layout() {
  // Ends the session on the server too, not just in this browser (#93).
  const clear = () => void logout();
  const { data: household } = useQuery({ queryKey: ["household"], queryFn: getCurrentHousehold });
  const [showingMore, setShowingMore] = useState(false);
  const location = useLocation();

  // Any navigation closes the sheet, including the browser's back button.
  useEffect(() => setShowingMore(false), [location.pathname]);

  useEffect(() => {
    if (!showingMore) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setShowingMore(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [showingMore]);

  const onAccountPage = ACCOUNT.some((entry) => location.pathname.startsWith(entry.to));

  return (
    <div className="shell">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      <aside className="shell-sidebar">
        <Link to="/" className="shell-brand">
          <img src="/icon-192.png" alt="" />
          <span>
            Trend &amp; Tend
            {household && <small>{household.name}</small>}
          </span>
        </Link>
        <nav className="shell-nav" aria-label="Main">
          {PRIMARY.map((entry) => (
            <NavItem key={entry.to} entry={entry} />
          ))}
        </nav>
        <nav className="shell-nav shell-nav-account" aria-label="Account">
          {ACCOUNT.map((entry) => (
            <NavItem key={entry.to} entry={entry} />
          ))}
          <button type="button" onClick={clear}>
            <Icon name="logout" />
            <span>Log out</span>
          </button>
        </nav>
      </aside>

      <header className="shell-topbar">
        <Link to="/" className="shell-brand">
          <img src="/icon-192.png" alt="" />
          <span>Trend &amp; Tend</span>
        </Link>
        {household && <span className="shell-topbar-household">{household.name}</span>}
      </header>

      <div className="shell-main">
        <main className="app-content" id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
        <LegalNotice />
      </div>

      <nav className="shell-tabbar" aria-label="Main">
        {PRIMARY.map((entry) => (
          <NavItem key={entry.to} entry={entry} />
        ))}
        <button
          type="button"
          className={onAccountPage || showingMore ? "active" : undefined}
          aria-expanded={showingMore}
          onClick={() => setShowingMore(!showingMore)}
        >
          <Icon name="more" />
          <span>More</span>
        </button>
      </nav>

      {showingMore && (
        <>
          <button type="button" className="shell-sheet-backdrop" aria-label="Close menu" onClick={() => setShowingMore(false)} />
          <nav className="shell-sheet" aria-label="More">
            {household && <span className="shell-sheet-title">{household.name}</span>}
            {ACCOUNT.map((entry) => (
              <NavItem key={entry.to} entry={entry} />
            ))}
            <button type="button" onClick={clear}>
              <Icon name="logout" />
              <span>Log out</span>
            </button>
          </nav>
        </>
      )}
    </div>
  );
}
