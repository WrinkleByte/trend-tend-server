// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * The "Appropriate Legal Notices" AGPL-3.0 §5(d) asks every interactive
 * screen to show, plus the §13 offer of source code to network users.
 *
 * If you run a modified version for other people, point SOURCE_URL at
 * your own modified source — that's what §13 requires of you — and see
 * TRADEMARKS.md about the name.
 */
const SOURCE_URL = "https://github.com/wrinklebyte/trend-tend-server";
const LICENSE_URL = "https://www.gnu.org/licenses/agpl-3.0.html";

export function LegalNotice() {
  return (
    <footer className="legal-notice">
      Trend &amp; Tend Server · © 2026 WrinkleByte LLC · Free software under the{" "}
      <a href={LICENSE_URL} target="_blank" rel="noreferrer">
        GNU AGPL v3
      </a>
      , with no warranty ·{" "}
      <a href={SOURCE_URL} target="_blank" rel="noreferrer">
        Source code
      </a>
    </footer>
  );
}
