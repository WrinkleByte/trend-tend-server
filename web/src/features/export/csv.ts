// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

function csvEscape(value: unknown): string {
  if (value === null || value === undefined) return '';
  const str = typeof value === 'object' ? JSON.stringify(value) : String(value);
  if (/["\n,]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export function toCSV<T extends object>(rows: T[]): string {
  if (rows.length === 0) return '';
  const columns = Object.keys(rows[0]) as (keyof T)[];
  const lines = rows.map(row => columns.map(col => csvEscape(row[col])).join(','));
  return [columns.join(','), ...lines].join('\r\n');
}
