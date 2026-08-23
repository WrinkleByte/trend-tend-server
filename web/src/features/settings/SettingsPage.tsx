import { useState } from "react";
import { AdminHouseholdsSection } from "./AdminHouseholdsSection";
import { ApiTokensPage } from "./ApiTokensPage";
import { DangerZoneSection } from "./DangerZoneSection";
import { DisplaySection } from "./DisplaySection";
import { InstanceSettingsSection } from "./InstanceSettingsSection";
import { UserManagementSection } from "./UserManagementSection";

const CATEGORIES = [
  { id: "smtp", label: "SMTP" },
  { id: "households", label: "Households" },
  { id: "users", label: "User Management" },
  { id: "api-tokens", label: "API Tokens" },
  { id: "display", label: "Display" },
  { id: "danger-zone", label: "Danger Zone" },
] as const;

type CategoryId = (typeof CATEGORIES)[number]["id"];

/** Settings page shell — a left-hand category sidebar replacing what used
 * to be one long-scrolling page (SMTP config, households, user
 * management, API tokens, display preferences all stacked on top of each
 * other). Each category's own section component still self-hides on a
 * 403 (non-instance-admin) exactly as it did before this split — this
 * shell only decides which one is showing, it doesn't add its own
 * permission gating. */
export function SettingsPage() {
  const [active, setActive] = useState<CategoryId>("smtp");

  return (
    <div>
      <h1>Settings</h1>
      <div className="settings-layout">
        <nav className="settings-sidebar">
          {CATEGORIES.map((category) => (
            <button
              key={category.id}
              type="button"
              className={category.id === active ? "active" : ""}
              onClick={() => setActive(category.id)}
            >
              {category.label}
            </button>
          ))}
        </nav>
        <div className="settings-content">
          {active === "smtp" && <InstanceSettingsSection />}
          {active === "households" && <AdminHouseholdsSection />}
          {active === "users" && <UserManagementSection />}
          {active === "api-tokens" && <ApiTokensPage />}
          {active === "display" && <DisplaySection />}
          {active === "danger-zone" && <DangerZoneSection />}
        </div>
      </div>
    </div>
  );
}
