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
          for (const { attachment, blob } of blobs) {
            // Named by id, not original_filename — two different attachments
            // can share a filename (e.g. two photos both named "IMG_001.jpg"),
            // but ids are always unique. A restore implementation matches
            // each attachments[] JSON row back to its file this same way, on
            // every platform, so this can't be a cosmetic-only choice.
            const extension = attachment.original_filename.includes('.')
              ? attachment.original_filename.slice(attachment.original_filename.lastIndexOf('.'))
              : '';
            zip.file(`attachments/${attachment.id}${extension}`, blob);
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
    <div className="page-narrow">
      <h1>Export</h1>
      <p>Download every record in your household — assets, fuel logs, service history, and maintenance schedules.</p>

      <section className="panel" style={{ marginTop: '20px' }}>
        <h3>Format</h3>
        <label className="check-label">
          <input type="radio" name="format" checked={format === 'json'} onChange={() => setFormat('json')} />
          JSON — a single structured backup file, full fidelity, best for re-importing later
        </label>
        <label className="check-label">
          <input type="radio" name="format" checked={format === 'csv'} onChange={() => setFormat('csv')} />
          CSV — one spreadsheet per record type, easy to open in Excel/Sheets
        </label>
        <label className="check-label" style={{ alignItems: 'flex-start', marginBottom: '16px' }}>
          <input
            type="radio"
            name="format"
            checked={format === 'fuelly'}
            onChange={() => setFormat('fuelly')}
            style={{ marginTop: '4px' }}
          />
          Fuelly CSV — fuel logs + service history combined into one file, formatted to re-import into Fuelly (or
          back into WrinkleByte)
        </label>

        <label className="check-label" style={{ alignItems: 'flex-start', marginBottom: 0 }}>
          <input
            type="checkbox"
            checked={includeAttachments}
            onChange={(e) => setIncludeAttachments(e.target.checked)}
            style={{ marginTop: '4px' }}
          />
          Include attachment files (receipts, photos) — downloads every file, may take a while
        </label>
      </section>

      <button onClick={handleExport} disabled={exporting}>
        {exporting
          ? progress
            ? `Downloading attachments... ${progress.done}/${progress.total}`
            : 'Exporting...'
          : 'Export My Data'}
      </button>

      {summary && (
        <div className="notice notice-success">
          <h3>Export complete</h3>
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
