// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, NavLink, Outlet } from "react-router-dom";
import { getCurrentHousehold } from "../../api/households";
import { useAuthStore } from "../../auth/authStore";
import { LegalNotice } from "../../components/LegalNotice";

function navLinkClass({ isActive }: { isActive: boolean }) {
  return isActive ? "active" : undefined;
}

export function Layout() {
  const clear = useAuthStore((s) => s.clear);
  const { data: household } = useQuery({ queryKey: ["household"], queryFn: getCurrentHousehold });
  // Mobile-only slide-out drawer (see App.css's ≤700px block) — the
  // hamburger button that toggles this is itself hidden above that
  // width, so this state is simply unused/inert on desktop rather than
  // needing its own width check here.
  const [showingMobileNav, setShowingMobileNav] = useState(false);

  // Escape-to-close. If the viewport is resized past the breakpoint
  // while the drawer is open (e.g. a tablet rotated to landscape),
  // App.css's ≤700px rule forces the drawer/backdrop/toggle to
  // `display: none` regardless of this state -- no resize listener
  // needed to avoid a "stuck open" drawer, the CSS handles it.
  useEffect(() => {
    if (!showingMobileNav) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setShowingMobileNav(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [showingMobileNav]);

  const navLinks = (
    <>
      <NavLink to="/" end className={navLinkClass} onClick={() => setShowingMobileNav(false)}>
        Assets
      </NavLink>
      <NavLink to="/household" className={navLinkClass} onClick={() => setShowingMobileNav(false)}>
        Household
      </NavLink>
      <NavLink to="/import" className={navLinkClass} onClick={() => setShowingMobileNav(false)}>
        Import
      </NavLink>
      <NavLink to="/export" className={navLinkClass} onClick={() => setShowingMobileNav(false)}>
        Export
      </NavLink>
      <NavLink to="/settings" className={navLinkClass} onClick={() => setShowingMobileNav(false)}>
        Settings
      </NavLink>
      <button
        type="button"
        onClick={() => {
          setShowingMobileNav(false);
          clear();
        }}
      >
        Log out
      </button>
    </>
  );

  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <header className="app-nav">
        <button
          type="button"
          className="mobile-nav-toggle"
          aria-label="Menu"
          aria-expanded={showingMobileNav}
          onClick={() => setShowingMobileNav(true)}
        >
          <span />
          <span />
          <span />
        </button>
        <Link to="/" className="brand">
          <img src="/icon-192.png" alt="" />
          Trend & Tend
        </Link>
        {household && <span className="household-name">{household.name}</span>}
        <nav className="app-nav-links">{navLinks}</nav>
      </header>
      {showingMobileNav && (
        <>
          <button
            type="button"
            className="mobile-nav-backdrop"
            aria-label="Close menu"
            onClick={() => setShowingMobileNav(false)}
          />
          <nav className="mobile-nav-drawer">
            {household && <span className="household-name">{household.name}</span>}
            {navLinks}
          </nav>
        </>
      )}
      <main className="app-content" id="main-content" tabIndex={-1}>
        <Outlet />
      </main>
      <LegalNotice />
    </div>
  );
}
