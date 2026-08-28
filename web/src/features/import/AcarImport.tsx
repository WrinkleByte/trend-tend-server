import JSZip from 'jszip';
import { useMemo, useRef, useState } from 'react';
import { createAsset } from '../../api/assets';
import { createFuelLogsBulk } from '../../api/fuelLogs';
import { createMaintenanceRecordsBulk } from '../../api/maintenanceRecords';
import type { Asset, AssetType, CreateFuelLogRequest, MaintenanceRecordCreateInput } from '../../api/types';
import { ASSET_TYPES } from '../assets/assetTypes';
import { StatusMessage } from "../../components/StatusMessage";

// aCar was a product later acquired by Fuelly (Vikunja #8) -- this mirrors
// FuellyImport.tsx's overall shape (parse -> group by vehicle -> per-group
// review/match-or-create -> import -> summary) and the mobile apps'
// AcarBackupParser.kt/AcarImportScreen.kt/AcarImportView.swift, which this
// is the web counterpart of. Unlike mobile (no XML/zip library in Kotlin
// common, hand-rolled MinimalXmlParser.kt + platform-side zip handling),
// the browser has DOMParser and this repo already depends on jszip (used
// by RestoreBackup.tsx), so both zip extraction and XML parsing are native
// here -- no hand-rolled parser needed.
//
// Deliberately does NOT import trip-records: the one real backup available
// while building this feature had zero trip-records (metadata.inf's
// acar.backup.data-count.trip-records=0), so there was no ground truth to
// verify aCar's trip-record field names against. See AcarBackupParser.kt's
// doc comment for the full rationale (shared across all three platforms).

const KM_PER_MILE = 1.609344;
const LITERS_PER_US_GALLON = 3.785411784;

type UnitSystem = 'imperial' | 'metric';

function distanceToMiles(value: number, system: UnitSystem): number {
  return system === 'metric' ? value / KM_PER_MILE : value;
}

function volumeToGallons(value: number, system: UnitSystem): number {
  return system === 'metric' ? value / LITERS_PER_US_GALLON : value;
}

function costPerVolumeToCostPerGallon(value: number, system: UnitSystem): number {
  return system === 'metric' ? value * LITERS_PER_US_GALLON : value;
}

// aCar's "Vehicle" is really just "thing this entry was for" (small engines
// as much as cars), same reasoning as FuellyImport.tsx's EQUIPMENT_HINTS --
// kept identical to that list for consistency between the two importers.
const EQUIPMENT_HINTS = [
  'generator', 'mower', 'snowblower', 'snow blower', 'chainsaw', 'chain saw',
  'trimmer', 'tractor', 'compressor', 'pump', 'tiller', 'blower', 'edger',
];

function guessAssetType(vehicleName: string): AssetType {
  const lower = vehicleName.toLowerCase();
  return EQUIPMENT_HINTS.some(hint => lower.includes(hint)) ? 'equipment' : 'vehicle';
}

// Web's fixed maintenance-category list (maintenanceAlerts.ts's
// RECORD_CATEGORIES) now mirrors mobile's full vocabulary -- these keys
// must match values actually in that list (e.g. "filters", not "filter").
// The backend doesn't enforce a category enum (plain string column), but
// guessing onto a category this app's own UI doesn't offer would be
// confusing to edit later.
const CATEGORY_KEYWORDS: [string, string][] = [
  ['oil', 'oil_change'],
  ['tire', 'tires'],
  ['filter', 'filters'],
  ['inspect', 'inspection'],
  ['clean', 'general_service'],
];

function guessMaintenanceCategory(acarServiceName: string): string {
  const lower = acarServiceName.toLowerCase();
  return CATEGORY_KEYWORDS.find(([keyword]) => lower.includes(keyword))?.[1] ?? 'custom';
}

interface ParsedAcarFuelLog {
  performedAt: string;
  odometerReading: number | null;
  gallons: number;
  costPerGallon: number | null;
  totalCost: number | null;
  isFillUp: boolean;
  gasBrand: string;
  notes: string;
}

interface ParsedAcarMaintenanceRecord {
  performedAt: string;
  odometerReading: number | null;
  category: string;
  customCategory: string | null;
  description: string | null;
  cost: number | null;
}

interface AcarVehicleGroup {
  vehicleName: string;
  assetType: AssetType;
  fuelLogs: ParsedAcarFuelLog[];
  maintenanceRecords: ParsedAcarMaintenanceRecord[];
}

interface AcarParseResult {
  vehicleGroups: AcarVehicleGroup[];
  skippedVehicleCount: number;
}

interface ImportSummary {
  fuelImported: number;
  fuelErrors: number;
  maintenanceImported: number;
  maintenanceErrors: number;
  vehiclesCreated: string[];
  vehiclesMatched: string[];
  errorDetails: string[];
}

function childText(el: Element | null | undefined, tag: string): string | null {
  const child = el?.querySelector(`:scope > ${tag}`);
  const text = child?.textContent?.trim();
  return text ? text : null;
}

function childFloat(el: Element | null | undefined, tag: string): number | null {
  const text = childText(el, tag);
  if (text === null) return null;
  const value = parseFloat(text);
  return Number.isNaN(value) ? null : value;
}

// aCar's record dates are "MM/dd/yyyy - HH:mm" (e.g. "10/02/2016 - 09:03")
// -- reformatted to this app's canonical "yyyy-MM-dd" (performed_at is a
// date-only field throughout this schema; the time-of-day component is
// discarded, same as every other date-entry path in this app). Falls back
// to the raw string if it doesn't match the expected shape, so a human can
// notice something's wrong rather than silently substituting a guess.
function parseAcarDateTime(raw: string | null): string {
  if (!raw) return '';
  const datePart = raw.split(' - ')[0]?.trim();
  const parts = datePart?.split('/');
  if (!parts || parts.length !== 3) return raw;
  const [month, day, year] = parts.map(p => parseInt(p, 10));
  if ([month, day, year].some(Number.isNaN)) return raw;
  const mm = String(month).padStart(2, '0');
  const dd = String(day).padStart(2, '0');
  return `${year}-${mm}-${dd}`;
}

// aCar keeps distance/volume/economy units in lockstep (no imperial-
// distance-with-metric-volume combination in its settings UI), so only the
// distance unit is checked. UK gallons are treated as US gallons -- a
// known, small approximation.
function detectUnitSystem(doc: XMLDocument | null): UnitSystem {
  if (!doc) return 'imperial';
  const pref = Array.from(doc.querySelectorAll('preference')).find(
    p => p.getAttribute('name') === 'acar.distance-unit',
  );
  return pref?.textContent?.trim().toLowerCase() === 'km' ? 'metric' : 'imperial';
}

// services.xml/expenses.xml are both flat id->name lookup tables
// (<service id="41"><name>A/C System</name>...) with the same shape under
// a different root/child tag name.
function parseNameLookup(doc: XMLDocument | null, elementName: string): Map<string, string> {
  const map = new Map<string, string>();
  if (!doc) return map;
  for (const el of Array.from(doc.querySelectorAll(elementName))) {
    const id = el.getAttribute('id');
    const name = childText(el, 'name');
    if (id && name) map.set(id, name);
  }
  return map;
}

function parseFillup(el: Element, unitSystem: UnitSystem): ParsedAcarFuelLog {
  const volume = childFloat(el, 'volume') ?? 0;
  const pricePerVolume = childFloat(el, 'price-per-volume-unit');
  const odometer = childFloat(el, 'odometer-reading');
  return {
    performedAt: parseAcarDateTime(childText(el, 'date')),
    odometerReading: odometer !== null ? Math.round(distanceToMiles(odometer, unitSystem)) : null,
    gallons: volumeToGallons(volume, unitSystem),
    costPerGallon: pricePerVolume !== null ? costPerVolumeToCostPerGallon(pricePerVolume, unitSystem) : null,
    totalCost: childFloat(el, 'total-cost'),
    // aCar's "partial" means NOT a full fill-up -- inverted from this
    // app's is_fill_up, which means "this fill-up reached full" (MPG is
    // only meaningful between two consecutive full fill-ups).
    isFillUp: childText(el, 'partial') !== 'true',
    gasBrand: childText(el, 'fuel-brand') ?? '',
    notes: childText(el, 'notes') ?? '',
  };
}

// service-record and expense-record share an identical shape (date,
// odometer, cost, notes, one-or-more type references) -- only the child
// element name differs ("services"/"service" vs. "expenses"/"expense").
// isExpense only controls whether a category-keyword guess is attempted
// (aCar's expense types -- Insurance, Tolls, Tax -- aren't maintenance
// categories, so guessing would misfile them; they always land in "custom"
// with the real expense-type name preserved in custom_category).
function parseServiceOrExpenseRecord(
  el: Element,
  groupTag: 'services' | 'expenses',
  nameLookup: Map<string, string>,
  unitSystem: UnitSystem,
  isExpense: boolean,
): ParsedAcarMaintenanceRecord {
  const itemTag = groupTag === 'services' ? 'service' : 'expense';
  const group = el.querySelector(`:scope > ${groupTag}`);
  const refs = group ? Array.from(group.querySelectorAll(itemTag)) : [];
  const names = refs
    .map(ref => ref.getAttribute('id'))
    .filter((id): id is string => id !== null)
    .map(id => nameLookup.get(id))
    .filter((name): name is string => name !== undefined);
  const combinedName = names.length > 0 ? names.join(', ') : null;
  const category = !isExpense && combinedName ? guessMaintenanceCategory(combinedName) : 'custom';
  const odometer = childFloat(el, 'odometer-reading');

  return {
    performedAt: parseAcarDateTime(childText(el, 'date')),
    odometerReading: odometer !== null ? Math.round(distanceToMiles(odometer, unitSystem)) : null,
    category,
    customCategory: category === 'custom' ? combinedName : null,
    description: childText(el, 'notes'),
    cost: childFloat(el, 'total-cost'),
  };
}

async function parseAcarBackup(file: File): Promise<AcarParseResult> {
  const zip = await JSZip.loadAsync(file);
  const vehiclesEntry = zip.file('vehicles.xml');
  if (!vehiclesEntry) throw new Error('Missing vehicles.xml in aCar backup');

  const parser = new DOMParser();
  const readXml = async (name: string): Promise<XMLDocument | null> => {
    const entry = zip.file(name);
    if (!entry) return null;
    const text = await entry.async('text');
    return parser.parseFromString(text, 'text/xml');
  };

  const [vehiclesDoc, preferencesDoc, servicesDoc, expensesDoc] = await Promise.all([
    vehiclesEntry.async('text').then(text => parser.parseFromString(text, 'text/xml')),
    readXml('preferences.xml'),
    readXml('services.xml'),
    readXml('expenses.xml'),
  ]);

  const unitSystem = detectUnitSystem(preferencesDoc);
  const serviceNames = parseNameLookup(servicesDoc, 'service');
  const expenseNames = parseNameLookup(expensesDoc, 'expense');

  let skipped = 0;
  const vehicleGroups: AcarVehicleGroup[] = [];
  for (const vehicleEl of Array.from(vehiclesDoc.querySelectorAll('vehicle'))) {
    const name = childText(vehicleEl, 'name');
    if (!name) {
      skipped++;
      continue;
    }

    const fillupRecords = Array.from(vehicleEl.querySelectorAll(':scope > fillup-records > fillup-record'));
    const serviceRecords = Array.from(vehicleEl.querySelectorAll(':scope > service-records > service-record'));
    const expenseRecords = Array.from(vehicleEl.querySelectorAll(':scope > expense-records > expense-record'));

    vehicleGroups.push({
      vehicleName: name,
      assetType: guessAssetType(name),
      fuelLogs: fillupRecords.map(el => parseFillup(el, unitSystem)),
      maintenanceRecords: [
        ...serviceRecords.map(el => parseServiceOrExpenseRecord(el, 'services', serviceNames, unitSystem, false)),
        ...expenseRecords.map(el => parseServiceOrExpenseRecord(el, 'expenses', expenseNames, unitSystem, true)),
      ],
    });
  }

  return { vehicleGroups, skippedVehicleCount: skipped };
}

function toFuelLogRequest(assetId: string, log: ParsedAcarFuelLog): CreateFuelLogRequest {
  return {
    asset_id: assetId,
    performed_at: log.performedAt,
    odometer_reading: log.odometerReading,
    gallons: log.gallons.toFixed(3),
    cost_per_gallon: log.costPerGallon !== null ? log.costPerGallon.toFixed(3) : null,
    total_cost: log.totalCost !== null ? log.totalCost.toFixed(2) : null,
    is_fill_up: log.isFillUp,
    gas_brand: log.gasBrand || null,
    notes: log.notes || null,
  };
}

function toMaintenanceRequest(assetId: string, record: ParsedAcarMaintenanceRecord): MaintenanceRecordCreateInput {
  return {
    asset_id: assetId,
    performed_at: record.performedAt,
    category: record.category,
    custom_category: record.customCategory,
    description: record.description,
    cost: record.cost,
    odometer_reading: record.odometerReading,
  };
}

const emptySummary = (): ImportSummary => ({
  fuelImported: 0,
  fuelErrors: 0,
  maintenanceImported: 0,
  maintenanceErrors: 0,
  vehiclesCreated: [],
  vehiclesMatched: [],
  errorDetails: [],
});

export function AcarImport({ assets, onAssetsCreated }: { assets: Asset[]; onAssetsCreated?: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [parseResult, setParseResult] = useState<AcarParseResult | null>(null);
  const [newAssetTypes, setNewAssetTypes] = useState<Record<string, AssetType>>({});
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<ImportSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const matchAsset = (vehicleName: string): Asset | undefined =>
    assets.find(a => a.name.trim().toLowerCase() === vehicleName.trim().toLowerCase());

  const assetTypeFor = (group: AcarVehicleGroup): AssetType => newAssetTypes[group.vehicleName] ?? group.assetType;

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setResult(null);
    setError(null);
    setNewAssetTypes({});
    setParseResult(null);

    try {
      const parsed = await parseAcarBackup(selectedFile);
      setParseResult(parsed);
    } catch (err) {
      console.error('Failed to parse aCar backup:', err);
      setError("Couldn't read that file as an aCar backup (.abp).");
    }
  };

  const handleImport = async () => {
    if (!parseResult || parseResult.vehicleGroups.length === 0) return;

    setImporting(true);
    setResult(null);

    try {
      const summary = emptySummary();
      for (const group of parseResult.vehicleGroups) {
        let asset = matchAsset(group.vehicleName);
        if (asset) {
          summary.vehiclesMatched.push(group.vehicleName);
        } else {
          asset = await createAsset({ asset_type: assetTypeFor(group), name: group.vehicleName });
          summary.vehiclesCreated.push(group.vehicleName);
        }

        const fuelResult = await createFuelLogsBulk(group.fuelLogs.map(log => toFuelLogRequest(asset.id, log)));
        summary.fuelImported += fuelResult.imported;
        summary.fuelErrors += fuelResult.errors;
        summary.errorDetails.push(...fuelResult.errorDetails);

        const maintenanceResult = await createMaintenanceRecordsBulk(
          group.maintenanceRecords.map(record => toMaintenanceRequest(asset.id, record)),
        );
        summary.maintenanceImported += maintenanceResult.imported;
        summary.maintenanceErrors += maintenanceResult.errors;
        summary.errorDetails.push(...maintenanceResult.errorDetails);
      }

      setResult(summary);
      if (summary.vehiclesCreated.length > 0) {
        onAssetsCreated?.();
      }
    } catch (err) {
      console.error('Import failed:', err);
      alert('Import failed. Check console for details.');
    } finally {
      setImporting(false);
    }
  };

  const totalRecords = useMemo(
    () =>
      parseResult?.vehicleGroups.reduce(
        (sum, group) => sum + group.fuelLogs.length + group.maintenanceRecords.length,
        0,
      ) ?? 0,
    [parseResult],
  );

  return (
    <section className="panel">
      <h2>Import from aCar backup</h2>
      <p>Bring in your vehicles, fuel-ups, service history, and other expenses from an aCar backup (.abp) file.</p>

      <div style={{ marginTop: '16px' }}>
        <h3>Step 1: Select aCar backup file</h3>
        <input
          ref={fileInputRef}
          type="file"
          accept=".abp"
          onChange={handleFileChange}
          style={{ marginBottom: '10px' }}
        />
        {file && <p>✓ File selected: {file.name}</p>}
        {error && <StatusMessage>{error}</StatusMessage>}
      </div>

      {parseResult && parseResult.vehicleGroups.length > 0 && (
        <div style={{ marginTop: '20px' }}>
          <h3>Step 2: Review</h3>
          <p>
            Found {totalRecords} record{totalRecords === 1 ? '' : 's'} across {parseResult.vehicleGroups.length}{' '}
            vehicle{parseResult.vehicleGroups.length === 1 ? '' : 's'}.
            {parseResult.skippedVehicleCount > 0 &&
              ` Skipped ${parseResult.skippedVehicleCount} unnamed vehicle${parseResult.skippedVehicleCount === 1 ? '' : 's'}.`}
          </p>

          <ul style={{ marginTop: '10px', listStyle: 'none', padding: 0 }}>
            {parseResult.vehicleGroups.map(group => {
              const matched = matchAsset(group.vehicleName);
              return (
                <li key={group.vehicleName} style={{ marginBottom: '8px' }}>
                  <strong>{group.vehicleName}</strong> — {group.fuelLogs.length} fuel,{' '}
                  {group.maintenanceRecords.length} service/expense —{' '}
                  {matched ? (
                    `will import into existing "${matched.name}" (${matched.asset_type})`
                  ) : (
                    <>
                      will create a new{' '}
                      <select
                        value={assetTypeFor(group)}
                        onChange={(e) =>
                          setNewAssetTypes(prev => ({ ...prev, [group.vehicleName]: e.target.value as AssetType }))
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
        </div>
      )}

      {parseResult && totalRecords > 0 && (
        <div style={{ marginTop: '20px' }}>
          <h3>Step 3: Import</h3>
          <button onClick={handleImport} disabled={importing}>
            {importing ? 'Importing...' : `Import ${totalRecords} records (${parseResult.vehicleGroups.length} assets)`}
          </button>
        </div>
      )}

      {result && (
        <div className="notice notice-success">
          <h3>Import complete</h3>
          <p>✓ Fuel logs imported: {result.fuelImported}</p>
          {result.fuelErrors > 0 && <p>✗ Fuel log errors: {result.fuelErrors}</p>}
          <p>✓ Service/expense records imported: {result.maintenanceImported}</p>
          {result.maintenanceErrors > 0 && <p>✗ Service/expense record errors: {result.maintenanceErrors}</p>}
          {result.vehiclesCreated.length > 0 && <p>+ Created assets: {result.vehiclesCreated.join(', ')}</p>}
          {result.vehiclesMatched.length > 0 && <p>Matched existing assets: {result.vehiclesMatched.join(', ')}</p>}
          {result.errorDetails.length > 0 && (
            <>
              <p>Rows that failed to import:</p>
              <ul>
                {result.errorDetails.map((detail, i) => (
                  <li key={i}>{detail}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  );
}
