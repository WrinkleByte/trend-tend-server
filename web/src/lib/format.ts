// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

/** "$1,234.50". Costs arrive from the API as decimal strings. */
export function formatMoney(value: number | string | null | undefined): string {
  const n = Number(value ?? 0);
  return (Number.isFinite(n) ? n : 0).toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
  });
}

/** "Oct 5, 2026" from a YYYY-MM-DD date. Parsed as a local date: handing the
 * bare string to Date() reads it as UTC midnight, which shows the previous
 * day anywhere west of Greenwich. */
export function formatDate(isoDate: string | null | undefined): string {
  if (!isoDate) return "";
  const [y, m, d] = isoDate.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return isoDate;
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
