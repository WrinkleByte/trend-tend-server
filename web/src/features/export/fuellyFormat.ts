import type { ExportBundle } from '../../api/export';

// Column order matches Fuelly's own CSV export exactly, so this file can be
// re-imported into Fuelly or re-imported into Tendfida's own Fuelly
// importer (see features/import/FuellyImport.tsx) unchanged.
const FUELLY_COLUMNS = [
  'Type', 'MPG', 'Date', 'Time', 'Vehicle', 'Odometer', 'Filled Up', 'Cost/Gallon', 'Gallons',
  'Total Cost', 'Octane', 'Gas Brand', 'Location', 'Tags', 'Payment Type', 'Tire Pressure', 'Notes', 'Services',
] as const;

type FuellyRow = Record<(typeof FUELLY_COLUMNS)[number], string>;

function fuellyEscape(value: string): string {
  if (/["\n,]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
  return value;
}

// Decimal fields (fuel log cost/gallon/total, maintenance record cost) come
// back from the backend as Decimal strings (e.g. "3.499"), so we just
// prefix them rather than round-tripping through Number() and risking a
// precision change.
function dollarsOrBlank(value: string | null): string {
  return value ? `$${value}` : '';
}

function dollarsOrZero(value: string | null): string {
  return value ? `$${value}` : '$0.00';
}

function odometerCell(value: number | null): string {
  return value != null ? value.toLocaleString('en-US') : '';
}

export function buildFuellyCSV(bundle: ExportBundle): string {
  const assetName = new Map(bundle.assets.map((asset) => [asset.id, asset.name]));
  const rows: FuellyRow[] = [];

  for (const log of bundle.fuel_logs) {
    rows.push({
      Type: 'Gas',
      MPG: log.mpg ?? '0.0',
      Date: log.performed_at,
      Time: '',
      Vehicle: assetName.get(log.asset_id) ?? '',
      Odometer: odometerCell(log.odometer_reading),
      'Filled Up': log.is_fill_up ? 'Full' : '',
      'Cost/Gallon': dollarsOrBlank(log.cost_per_gallon),
      Gallons: log.gallons ?? '0.000',
      'Total Cost': dollarsOrBlank(log.total_cost),
      Octane: log.octane != null ? String(log.octane) : '',
      'Gas Brand': log.gas_brand ?? '',
      Location: log.location ?? '',
      Tags: '',
      'Payment Type': '',
      'Tire Pressure': '',
      Notes: log.notes ?? '',
      Services: '',
    });
  }

  for (const record of bundle.maintenance_records) {
    rows.push({
      Type: 'Service',
      MPG: '0',
      Date: record.performed_at,
      Time: '',
      Vehicle: assetName.get(record.asset_id) ?? '',
      Odometer: odometerCell(record.odometer_reading),
      'Filled Up': '',
      'Cost/Gallon': '$0.00',
      Gallons: '0.000',
      'Total Cost': dollarsOrZero(record.cost),
      Octane: '',
      'Gas Brand': '',
      Location: '',
      Tags: '',
      'Payment Type': '',
      'Tire Pressure': '',
      Notes: record.description ?? '',
      // The Fuelly importer stashes the original "Services" text in
      // custom_category on the way in, so a Fuelly-sourced record round
      // trips exactly. Natively-created records fall back to their category.
      Services: record.custom_category || record.category.replace(/_/g, ' '),
    });
  }

  rows.sort((a, b) => a.Date.localeCompare(b.Date));

  const header = FUELLY_COLUMNS.map(fuellyEscape).join(',');
  const lines = rows.map((row) => FUELLY_COLUMNS.map((col) => fuellyEscape(row[col])).join(','));
  return [header, ...lines].join('\r\n');
}
