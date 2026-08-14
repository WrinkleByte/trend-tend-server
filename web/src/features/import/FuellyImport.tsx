import { useMemo, useRef, useState } from 'react';
import { createAsset } from '../../api/assets';
import { createFuelLogsBulk } from '../../api/fuelLogs';
import { createMaintenanceRecordsBulk } from '../../api/maintenanceRecords';
import type { Asset, AssetType, CreateFuelLogRequest, MaintenanceRecordCreateInput } from '../../api/types';
import { ASSET_TYPES } from '../assets/assetTypes';

// Fuelly's "Vehicle" column is really just "thing this entry was for" —
// Fuelly is used for small engines (mowers, generators) as much as cars, so
// we can't assume every entry is asset_type "vehicle". This is only a
// starting guess; the UI lets the user override it per entry before create.
const EQUIPMENT_HINTS = [
  'generator', 'mower', 'snowblower', 'snow blower', 'chainsaw', 'chain saw',
  'trimmer', 'tractor', 'compressor', 'pump', 'tiller', 'blower', 'edger',
];

function guessAssetType(vehicleName: string): AssetType {
  const lower = vehicleName.toLowerCase();
  return EQUIPMENT_HINTS.some(hint => lower.includes(hint)) ? 'equipment' : 'vehicle';
}

// Best-effort mapping from Fuelly's free-text "Services" list to this app's
// maintenance categories. The original Fuelly text is preserved in
// custom_category regardless, so nothing is lost if the guess is wrong.
function guessMaintenanceCategory(servicesText: string): string {
  const lower = servicesText.toLowerCase();
  if (lower.includes('oil')) return 'oil_change';
  if (lower.includes('tire')) return 'tires';
  if (lower.includes('filter')) return 'filter';
  if (lower.includes('inspect')) return 'inspection';
  if (lower.includes('clean')) return 'cleaning';
  return 'other';
}

interface ParsedFuelLog {
  vehicle: string;
  performed_at: string;
  odometer_reading: number;
  gallons: string;
  mpg: string;
  cost_per_gallon: string;
  total_cost: string;
  is_fill_up: boolean;
  octane: number | null;
  gas_brand: string;
  location: string;
  notes: string;
}

interface ParsedMaintenanceRecord {
  vehicle: string;
  performed_at: string;
  odometer_reading: number | null;
  category: string;
  custom_category: string | null;
  description: string | null;
  cost: number | null;
}

interface ParseResult {
  fuelLogs: ParsedFuelLog[];
  maintenanceRecords: ParsedMaintenanceRecord[];
  skippedRowCount: number;
}

interface VehicleGroup {
  fuelLogs: ParsedFuelLog[];
  maintenanceRecords: ParsedMaintenanceRecord[];
}

type ImportMode = 'all' | 'specific';

interface ImportSummary {
  fuelImported: number;
  fuelErrors: number;
  maintenanceImported: number;
  maintenanceErrors: number;
  vehiclesCreated: string[];
  vehiclesMatched: string[];
}

// RFC4180-ish parser: Fuelly's export quotes fields that contain embedded
// commas and newlines (e.g. multi-line service notes), so a naive
// split('\n') mis-aligns every row that follows one of those fields.
function parseCSV(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = '';
  let inQuotes = false;
  let i = 0;
  const len = text.length;

  while (i < len) {
    const char = text[i];

    if (inQuotes) {
      if (char === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i += 2;
          continue;
        }
        inQuotes = false;
        i++;
        continue;
      }
      field += char;
      i++;
      continue;
    }

    if (char === '"') {
      inQuotes = true;
      i++;
      continue;
    }
    if (char === ',') {
      row.push(field);
      field = '';
      i++;
      continue;
    }
    if (char === '\r') {
      i++;
      continue;
    }
    if (char === '\n') {
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
      i++;
      continue;
    }
    field += char;
    i++;
  }

  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }

  return rows;
}

function parseFuellyCSV(csvText: string): ParseResult {
  const rows = parseCSV(csvText);
  if (rows.length === 0) return { fuelLogs: [], maintenanceRecords: [], skippedRowCount: 0 };

  const headers = rows[0].map(h => h.trim());
  const fuelLogs: ParsedFuelLog[] = [];
  const maintenanceRecords: ParsedMaintenanceRecord[] = [];
  let skippedRowCount = 0;

  for (let i = 1; i < rows.length; i++) {
    const values = rows[i];
    if (values.length === 1 && values[0].trim() === '') continue;

    const row: Record<string, string> = {};
    headers.forEach((header, idx) => {
      row[header] = (values[idx] ?? '').trim();
    });

    const vehicle = row['Vehicle'] || 'Unknown Vehicle';

    if (row['Type'] === 'Gas') {
      if (!row['Odometer'] || row['Odometer'] === '0') {
        skippedRowCount++;
        continue;
      }

      const octane = parseInt(row['Octane'], 10);

      fuelLogs.push({
        vehicle,
        performed_at: row['Date'] || '',
        odometer_reading: parseInt(row['Odometer'].replace(/,/g, ''), 10) || 0,
        gallons: row['Gallons'] || '0',
        mpg: row['MPG'] || '0',
        cost_per_gallon: (row['Cost/Gallon'] || '').replace('$', '') || '0',
        total_cost: (row['Total Cost'] || '').replace('$', '') || '0',
        is_fill_up: row['Filled Up'] === 'Full',
        octane: Number.isNaN(octane) ? null : octane,
        gas_brand: row['Gas Brand'] || '',
        location: row['Location'] || '',
        notes: row['Notes'] || '',
      });
    } else if (row['Type'] === 'Service') {
      const odometerNum = parseInt((row['Odometer'] || '').replace(/,/g, ''), 10);
      const costNum = parseFloat((row['Total Cost'] || '').replace('$', ''));
      const services = row['Services'] || '';

      maintenanceRecords.push({
        vehicle,
        performed_at: row['Date'] || '',
        odometer_reading: Number.isNaN(odometerNum) || odometerNum === 0 ? null : odometerNum,
        category: guessMaintenanceCategory(services),
        custom_category: services ? services.slice(0, 100) : null,
        description: row['Notes'] || null,
        cost: Number.isNaN(costNum) ? null : costNum,
      });
    } else {
      skippedRowCount++;
    }
  }

  return { fuelLogs, maintenanceRecords, skippedRowCount };
}

function toFuelLogRequest(assetId: string, log: ParsedFuelLog): CreateFuelLogRequest {
  return {
    asset_id: assetId,
    performed_at: log.performed_at,
    odometer_reading: log.odometer_reading,
    gallons: log.gallons,
    mpg: log.mpg,
    cost_per_gallon: log.cost_per_gallon,
    total_cost: log.total_cost,
    is_fill_up: log.is_fill_up,
    octane: log.octane,
    gas_brand: log.gas_brand || null,
    location: log.location || null,
    notes: log.notes || null,
  };
}

function toMaintenanceRequest(assetId: string, record: ParsedMaintenanceRecord): MaintenanceRecordCreateInput {
  return {
    asset_id: assetId,
    performed_at: record.performed_at,
    category: record.category,
    custom_category: record.custom_category,
    description: record.description,
    cost: record.cost,
    odometer_reading: record.odometer_reading,
  };
}

const emptySummary = (): ImportSummary => ({
  fuelImported: 0,
  fuelErrors: 0,
  maintenanceImported: 0,
  maintenanceErrors: 0,
  vehiclesCreated: [],
  vehiclesMatched: [],
});

export function FuellyImport({ assets, onAssetsCreated }: { assets: Asset[]; onAssetsCreated?: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  const [mode, setMode] = useState<ImportMode>('all');
  const [selectedCsvVehicle, setSelectedCsvVehicle] = useState<string>('');
  const [selectedAsset, setSelectedAsset] = useState<string>('');
  const [newAssetTypes, setNewAssetTypes] = useState<Record<string, AssetType>>({});
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<ImportSummary | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fuel logs and maintenance records aren't restricted to any one asset
  // type on the backend — a generator might be "equipment", an RV a
  // "vehicle", a whole-house backup generator a "home_system", etc. — so
  // any existing asset is a valid import target.
  const importableAssets = assets;

  const vehicleGroups = useMemo(() => {
    const groups = new Map<string, VehicleGroup>();
    const ensure = (name: string): VehicleGroup => {
      let group = groups.get(name);
      if (!group) {
        group = { fuelLogs: [], maintenanceRecords: [] };
        groups.set(name, group);
      }
      return group;
    };
    for (const log of parseResult?.fuelLogs ?? []) ensure(log.vehicle).fuelLogs.push(log);
    for (const record of parseResult?.maintenanceRecords ?? []) ensure(record.vehicle).maintenanceRecords.push(record);
    return groups;
  }, [parseResult]);

  const matchAsset = (vehicleName: string): Asset | undefined =>
    importableAssets.find(a => a.name.trim().toLowerCase() === vehicleName.trim().toLowerCase());

  const assetTypeFor = (vehicleName: string): AssetType => newAssetTypes[vehicleName] ?? guessAssetType(vehicleName);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setResult(null);
    setSelectedCsvVehicle('');
    setSelectedAsset('');
    setNewAssetTypes({});

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      const parsed = parseFuellyCSV(text);
      setParseResult(parsed);
      const firstVehicle = parsed.fuelLogs[0]?.vehicle ?? parsed.maintenanceRecords[0]?.vehicle ?? '';
      setSelectedCsvVehicle(firstVehicle);
    };
    reader.readAsText(selectedFile);
  };

  const importGroup = async (assetId: string, group: VehicleGroup, summary: ImportSummary) => {
    const fuelResult = await createFuelLogsBulk(group.fuelLogs.map(log => toFuelLogRequest(assetId, log)));
    summary.fuelImported += fuelResult.imported;
    summary.fuelErrors += fuelResult.errors;

    const maintenanceResult = await createMaintenanceRecordsBulk(
      group.maintenanceRecords.map(record => toMaintenanceRequest(assetId, record)),
    );
    summary.maintenanceImported += maintenanceResult.imported;
    summary.maintenanceErrors += maintenanceResult.errors;
  };

  const handleImportAll = async () => {
    const summary = emptySummary();

    for (const [vehicleName, group] of vehicleGroups) {
      let asset = matchAsset(vehicleName);
      if (asset) {
        summary.vehiclesMatched.push(vehicleName);
      } else {
        asset = await createAsset({ asset_type: assetTypeFor(vehicleName), name: vehicleName });
        summary.vehiclesCreated.push(vehicleName);
      }
      await importGroup(asset.id, group, summary);
    }

    return summary;
  };

  const handleImportSpecific = async () => {
    const summary = emptySummary();
    if (!selectedAsset || !selectedCsvVehicle) return summary;

    const group = vehicleGroups.get(selectedCsvVehicle) ?? { fuelLogs: [], maintenanceRecords: [] };
    await importGroup(selectedAsset, group, summary);
    const assetName = importableAssets.find(a => a.id === selectedAsset)?.name ?? selectedAsset;
    summary.vehiclesMatched.push(assetName);
    return summary;
  };

  const handleImport = async () => {
    if (!parseResult || (parseResult.fuelLogs.length === 0 && parseResult.maintenanceRecords.length === 0)) return;

    setImporting(true);
    setResult(null);

    try {
      const summary = mode === 'all' ? await handleImportAll() : await handleImportSpecific();
      setResult(summary);
      if (summary.vehiclesCreated.length > 0) {
        onAssetsCreated?.();
      }
    } catch (error) {
      console.error('Import failed:', error);
      alert('Import failed. Check console for details.');
    } finally {
      setImporting(false);
    }
  };

  const totalFuelLogs = parseResult?.fuelLogs.length ?? 0;
  const totalMaintenance = parseResult?.maintenanceRecords.length ?? 0;
  const totalRecords = totalFuelLogs + totalMaintenance;
  const canImport =
    totalRecords > 0 && (mode === 'all' ? vehicleGroups.size > 0 : Boolean(selectedAsset && selectedCsvVehicle));

  const selectedGroup = mode === 'specific' ? vehicleGroups.get(selectedCsvVehicle) : undefined;
  const selectedGroupCount = selectedGroup ? selectedGroup.fuelLogs.length + selectedGroup.maintenanceRecords.length : 0;

  return (
    <section className="panel">
      <h2>Import from Fuelly</h2>
      <p>Upload your Fuelly CSV export to import your fuel log and service history.</p>

      {/* Step 1: Upload File */}
      <div style={{ marginTop: '16px' }}>
        <h3>Step 1: Select CSV file</h3>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          onChange={handleFileChange}
          style={{ marginBottom: '10px' }}
        />
        {file && <p>✓ File selected: {file.name}</p>}
      </div>

      {/* Step 2: Review & choose import mode */}
      {parseResult && (
        <div style={{ marginTop: '20px' }}>
          <h3>Step 2: Choose import mode</h3>
          <p>
            Found {totalFuelLogs} fuel-up record{totalFuelLogs === 1 ? '' : 's'} and {totalMaintenance} service
            record{totalMaintenance === 1 ? '' : 's'} across {vehicleGroups.size} asset entr
            {vehicleGroups.size === 1 ? 'y' : 'ies'}.
            {parseResult.skippedRowCount > 0 &&
              ` Skipped ${parseResult.skippedRowCount} row${parseResult.skippedRowCount === 1 ? '' : 's'} (no odometer reading or unrecognized type).`}
          </p>

          <label style={{ display: 'block', marginBottom: '8px' }}>
            <input
              type="radio"
              name="mode"
              checked={mode === 'all'}
              onChange={() => setMode('all')}
              style={{ marginRight: '8px' }}
            />
            Import everything — match existing assets by name, create new ones automatically
          </label>
          <label style={{ display: 'block', marginBottom: '12px' }}>
            <input
              type="radio"
              name="mode"
              checked={mode === 'specific'}
              onChange={() => setMode('specific')}
              style={{ marginRight: '8px' }}
            />
            Import into one existing asset
          </label>

          {mode === 'all' && (
            <ul style={{ marginTop: '10px', listStyle: 'none', padding: 0 }}>
              {Array.from(vehicleGroups.entries()).map(([vehicleName, group]) => {
                const matched = matchAsset(vehicleName);
                return (
                  <li key={vehicleName} style={{ marginBottom: '8px' }}>
                    <strong>{vehicleName}</strong> — {group.fuelLogs.length} fuel, {group.maintenanceRecords.length}{' '}
                    service —{' '}
                    {matched ? (
                      `will import into existing "${matched.name}" (${matched.asset_type})`
                    ) : (
                      <>
                        will create a new{' '}
                        <select
                          value={assetTypeFor(vehicleName)}
                          onChange={(e) =>
                            setNewAssetTypes(prev => ({ ...prev, [vehicleName]: e.target.value as AssetType }))
                          }
                          style={{ padding: '2px 4px' }}
                        >
                          {ASSET_TYPES.map(t => (
                            <option key={t.value} value={t.value}>
                              {t.label.toLowerCase()}
                            </option>
                          ))}
                        </select>
                      </>
                    )}
                  </li>
                );
              })}
            </ul>
          )}

          {mode === 'specific' && (
            <div>
              {importableAssets.length === 0 ? (
                <p className="form-error">
                  You don't have any assets yet. Add one on the Assets page, or use "Import everything" above to
                  create them automatically from this file.
                </p>
              ) : (
                <>
                  <label style={{ display: 'block', marginBottom: '4px' }}>CSV entry</label>
                  <select
                    value={selectedCsvVehicle}
                    onChange={(e) => setSelectedCsvVehicle(e.target.value)}
                    style={{ width: '100%', padding: '8px', marginBottom: '10px' }}
                  >
                    {Array.from(vehicleGroups.entries()).map(([vehicleName, group]) => (
                      <option key={vehicleName} value={vehicleName}>
                        {vehicleName} ({group.fuelLogs.length} fuel, {group.maintenanceRecords.length} service)
                      </option>
                    ))}
                  </select>

                  <label style={{ display: 'block', marginBottom: '4px' }}>Import into</label>
                  <select
                    value={selectedAsset}
                    onChange={(e) => setSelectedAsset(e.target.value)}
                    style={{ width: '100%', padding: '8px', marginBottom: '10px' }}
                  >
                    <option value="">Select an asset...</option>
                    {importableAssets.map(asset => (
                      <option key={asset.id} value={asset.id}>
                        {asset.name} ({asset.asset_type})
                      </option>
                    ))}
                  </select>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* Step 3: Import */}
      {parseResult && totalRecords > 0 && (
        <div style={{ marginTop: '20px' }}>
          <h3>Step 3: Import</h3>
          <button onClick={handleImport} disabled={importing || !canImport}>
            {importing
              ? 'Importing...'
              : mode === 'all'
                ? `Import ${totalRecords} records (${vehicleGroups.size} assets)`
                : `Import ${selectedGroupCount} records`}
          </button>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="notice notice-success">
          <h3>Import complete</h3>
          <p>✓ Fuel logs imported: {result.fuelImported}</p>
          {result.fuelErrors > 0 && <p>✗ Fuel log errors: {result.fuelErrors}</p>}
          <p>✓ Service records imported: {result.maintenanceImported}</p>
          {result.maintenanceErrors > 0 && <p>✗ Service record errors: {result.maintenanceErrors}</p>}
          {result.vehiclesCreated.length > 0 && <p>+ Created assets: {result.vehiclesCreated.join(', ')}</p>}
          {result.vehiclesMatched.length > 0 && <p>Matched existing assets: {result.vehiclesMatched.join(', ')}</p>}
        </div>
      )}
    </section>
  );
}
