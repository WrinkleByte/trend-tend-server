// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useEffect, useState } from "react";

// Pure local UI preference, same pattern as assetPhotosSetting.ts — never
// synced, just which color scheme this browser renders in. "system" (the
// default) means no override: index.css's prefers-color-scheme media query
// decides. index.html has a small blocking script that applies a saved
// light/dark override before first paint, so switching tabs/reloading
// doesn't flash the wrong theme first.
export type ThemePreference = "system" | "light" | "dark";

const STORAGE_KEY = "theme";

function readStoredValue(): ThemePreference {
  if (typeof localStorage === "undefined") return "system";
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw === "light" || raw === "dark" ? raw : "system";
}

function applyTheme(theme: ThemePreference) {
  if (theme === "system") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.setAttribute("data-theme", theme);
  }
}

export function useThemePreference(): [ThemePreference, (value: ThemePreference) => void] {
  const [theme, setTheme] = useState(readStoredValue);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, theme);
    applyTheme(theme);
  }, [theme]);

  return [theme, setTheme];
}
