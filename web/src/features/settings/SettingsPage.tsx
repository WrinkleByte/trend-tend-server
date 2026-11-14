// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { NavLink, Navigate, useParams } from "react-router-dom";
import { PageHeader } from "../../components/ui/PageHeader";
import { DEFAULT_SETTINGS_SECTION, SETTINGS_GROUPS } from "./sections";
import { useIsInstanceAdmin } from "./useIsInstanceAdmin";

/** Settings shell: a grouped sidebar where every section has its own
 * address (/settings/<section>), so sections can be linked and the back
 * button works. The "Server" group is listed only for instance admins;
 * its sections still hide themselves on a 403, so reaching one by typing
 * the address shows nothing rather than an error. */
export function SettingsPage() {
  const { section } = useParams<{ section: string }>();
  const isAdmin = useIsInstanceAdmin();

  const groups = SETTINGS_GROUPS.filter((group) => !group.adminOnly || isAdmin);
  const active = SETTINGS_GROUPS.flatMap((group) => group.sections).find((s) => s.id === section);
  if (!active) return <Navigate to={`/settings/${DEFAULT_SETTINGS_SECTION}`} replace />;

  return (
    <div>
      <PageHeader title="Settings" />
      <div className="settings-layout">
        <nav className="settings-sidebar" aria-label="Settings sections">
          {groups.map((group) => (
            <div key={group.label} className="settings-group">
              <span className="settings-group-label">{group.label}</span>
              {group.sections.map((s) => (
                <NavLink key={s.id} to={`/settings/${s.id}`} className={({ isActive }) => (isActive ? "active" : undefined)}>
                  {s.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="settings-content">{active.element}</div>
      </div>
    </div>
  );
}
