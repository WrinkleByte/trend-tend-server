import { useState } from 'react';
import JSZip from 'jszip';
import { fetchAllAttachmentBlobs, gatherExportData } from '../../api/export';
import { toCSV } from './csv';
import { downloadBlob } from './downloadBlob';
import { buildFuellyCSV } from './fuellyFormat';

type ExportFormat = 'json' | 'csv' | 'fuelly';

interface ExportSummary {
  assets: number;
  fuelLogs: number;
  maintenanceRecords: number;
  maintenanceSchedules: number;
  attachments: number;
}

export function ExportPage() {
  const [format, setFormat] = useState<ExportFormat>('json');
  const [includeAttachments, setIncludeAttachments] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [summary, setSummary] = useState<ExportSummary | null>(null);

  const handleExport = async () => {
    setExporting(true);
    setProgress(null);
    setSummary(null);

    try {
      const bundle = await gatherExportData();
      const dateStr = new Date().toISOString().slice(0, 10);
      // CSV format is always multiple files, so it always needs a zip; JSON
      // and Fuelly format are single files unless attachments are along for
      // the ride too.
      const needsZip = format === 'csv' || includeAttachments;

      if (!needsZip) {
        if (format === 'json') {
          downloadBlob(
            new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' }),
            `wrinklebyte-export-${dateStr}.json`,
          );
        } else {
          downloadBlob(
            new Blob([buildFuellyCSV(bundle)], { type: 'text/csv' }),
            `wrinklebyte-fuelly-export-${dateStr}.csv`,
          );
        }
      } else {
        const zip = new JSZip();

        if (format === 'json') {
          zip.file('data.json', JSON.stringify(bundle, null, 2));
        } else if (format === 'fuelly') {
          zip.file('fuelly-export.csv', buildFuellyCSV(bundle));
        } else {
          zip.file('assets.csv', toCSV(bundle.assets));
          zip.file('fuel_logs.csv', toCSV(bundle.fuel_logs));
          zip.file('maintenance_records.csv', toCSV(bundle.maintenance_records));
          zip.file('maintenance_schedules.csv', toCSV(bundle.maintenance_schedules));
          zip.file('attachments.csv', toCSV(bundle.attachments));
        }

        if (includeAttachments && bundle.attachments.length > 0) {
          setProgress({ done: 0, total: bundle.attachments.length });
          const blobs = await fetchAllAttachmentBlobs(bundle.attachments, (done, total) =>
            setProgress({ done, total }),
          );
          const usedNames = new Set<string>();
          for (const { attachment, blob } of blobs) {
            let name = attachment.original_filename || attachment.id;
            if (usedNames.has(name)) name = `${attachment.id}-${name}`;
            usedNames.add(name);
            zip.file(`attachments/${name}`, blob);
          }
        }

        const zipBlob = await zip.generateAsync({ type: 'blob' });
        downloadBlob(zipBlob, `wrinklebyte-export-${dateStr}.zip`);
      }

      setSummary({
        assets: bundle.assets.length,
        fuelLogs: bundle.fuel_logs.length,
        maintenanceRecords: bundle.maintenance_records.length,
        maintenanceSchedules: bundle.maintenance_schedules.length,
        attachments: includeAttachments ? bundle.attachments.length : 0,
      });
    } catch (error) {
      console.error('Export failed:', error);
      alert('Export failed. Check console for details.');
    } finally {
      setExporting(false);
      setProgress(null);
    }
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto', padding: '20px' }}>
      <h2>Export Your Data</h2>
      <p>Download every record in your household — assets, fuel logs, service history, and maintenance schedules.</p>

      <div style={{ marginBottom: '20px', padding: '20px', border: '1px solid #ddd', borderRadius: '8px' }}>
        <h3>Format</h3>
        <label style={{ display: 'block', marginBottom: '8px' }}>
          <input
            type="radio"
            name="format"
            checked={format === 'json'}
            onChange={() => setFormat('json')}
            style={{ marginRight: '8px' }}
          />
          JSON — a single structured backup file, full fidelity, best for re-importing later
        </label>
        <label style={{ display: 'block', marginBottom: '8px' }}>
          <input
            type="radio"
            name="format"
            checked={format === 'csv'}
            onChange={() => setFormat('csv')}
            style={{ marginRight: '8px' }}
          />
          CSV — one spreadsheet per record type, easy to open in Excel/Sheets
        </label>
        <label style={{ display: 'block', marginBottom: '12px' }}>
          <input
            type="radio"
            name="format"
            checked={format === 'fuelly'}
            onChange={() => setFormat('fuelly')}
            style={{ marginRight: '8px' }}
          />
          Fuelly CSV — fuel logs + service history combined into one file, formatted to re-import into Fuelly (or
          back into WrinkleByte)
        </label>

        <label style={{ display: 'block' }}>
          <input
            type="checkbox"
            checked={includeAttachments}
            onChange={(e) => setIncludeAttachments(e.target.checked)}
            style={{ marginRight: '8px' }}
          />
          Include attachment files (receipts, photos) — downloads every file, may take a while
        </label>
      </div>

      <button
        onClick={handleExport}
        disabled={exporting}
        style={{
          padding: '12px 24px',
          backgroundColor: exporting ? '#ccc' : '#007bff',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: exporting ? 'not-allowed' : 'pointer',
          fontSize: '16px',
        }}
      >
        {exporting
          ? progress
            ? `Downloading attachments... ${progress.done}/${progress.total}`
            : 'Exporting...'
          : 'Export My Data'}
      </button>

      {summary && (
        <div
          style={{
            marginTop: '20px',
            padding: '20px',
            border: '2px solid #28a745',
            borderRadius: '8px',
            backgroundColor: '#d4edda',
          }}
        >
          <h3>Export Complete!</h3>
          <p>
            {summary.assets} assets, {summary.fuelLogs} fuel logs, {summary.maintenanceRecords} maintenance
            records, {summary.maintenanceSchedules} maintenance schedules
            {summary.attachments > 0 && `, ${summary.attachments} attachment files`}.
          </p>
        </div>
      )}
    </div>
  );
}
