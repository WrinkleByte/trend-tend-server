import { useRef, useState } from 'react';
import { ApiError } from '../../api/client';
import { restoreBackup, type RestoreConflict, type RestoreSummary } from '../../api/restore';

interface RestoreState {
  status: 'idle' | 'restoring' | 'conflict' | 'success' | 'error';
  conflict?: RestoreConflict;
  summary?: RestoreSummary;
  errorMessage?: string;
}

function parseConflict(error: ApiError): RestoreConflict | null {
  try {
    const body = JSON.parse(error.message);
    return body?.detail ?? null;
  } catch {
    return null;
  }
}

interface RestoreBackupProps {
  onRestored: () => void;
}

export function RestoreBackup({ onRestored }: RestoreBackupProps) {
  const [state, setState] = useState<RestoreState>({ status: 'idle' });
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pendingFileRef = useRef<File | null>(null);

  const runRestore = async (file: File, force: boolean) => {
    setState({ status: 'restoring' });
    try {
      const summary = await restoreBackup(file, force);
      setState({ status: 'success', summary });
      onRestored();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        const conflict = parseConflict(error);
        if (conflict) {
          pendingFileRef.current = file;
          setState({ status: 'conflict', conflict });
          return;
        }
      }
      setState({
        status: 'error',
        errorMessage: error instanceof ApiError ? error.message : 'Restore failed. Check console for details.',
      });
      console.error('Restore failed:', error);
    }
  };

  const handleFileChosen = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = ''; // allow re-choosing the same file after a failed attempt
    if (!file) return;
    void runRestore(file, false);
  };

  const handleConfirmOverride = () => {
    const file = pendingFileRef.current;
    if (!file) return;
    void runRestore(file, true);
  };

  const handleCancelOverride = () => {
    pendingFileRef.current = null;
    setState({ status: 'idle' });
  };

  return (
    <div style={{ marginBottom: '20px', padding: '20px', border: '1px solid #ddd', borderRadius: '8px' }}>
      <h3>Restore from Backup</h3>
      <p>
        Seed this household from a JSON backup zip (produced by the Export page, mobile or web). Every restored
        record gets a brand-new id — this <strong>adds</strong> data, it does not merge or overwrite by matching
        against the backup's original records.
      </p>
      <p style={{ color: '#856404', backgroundColor: '#fff3cd', padding: '10px', borderRadius: '4px' }}>
        This is for seeding a household that has no data yet — recovering a device that's still connected to a
        household with existing data should use that connection's normal sync instead, not this. Restoring into a
        household that already has data risks visible duplicates (see the override warning below).
      </p>

      <input
        ref={fileInputRef}
        type="file"
        accept=".zip"
        onChange={handleFileChosen}
        disabled={state.status === 'restoring'}
      />

      {state.status === 'restoring' && <p>Restoring...</p>}

      {state.status === 'conflict' && state.conflict && (
        <div
          style={{
            marginTop: '16px',
            padding: '16px',
            border: '2px solid #dc3545',
            borderRadius: '8px',
            backgroundColor: '#f8d7da',
          }}
        >
          <h4>This household already has data</h4>
          <p>
            {state.conflict.existing_assets} assets, {state.conflict.existing_fuel_logs} fuel logs,{' '}
            {state.conflict.existing_maintenance_records} maintenance records,{' '}
            {state.conflict.existing_maintenance_schedules} maintenance schedules already exist here.
          </p>
          <p>
            <strong>Restoring anyway will not merge or replace this data — it adds the backup's records
            alongside what's already here.</strong> If the backup and the existing data overlap (e.g. this is the
            same household restored from an old snapshot), you will end up with duplicates of everything that
            overlaps. Only continue if you specifically intend that.
          </p>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              onClick={handleConfirmOverride}
              style={{
                padding: '10px 20px',
                backgroundColor: '#dc3545',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              Restore Anyway (may create duplicates)
            </button>
            <button
              onClick={handleCancelOverride}
              style={{
                padding: '10px 20px',
                backgroundColor: '#6c757d',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {state.status === 'success' && state.summary && (
        <div
          style={{
            marginTop: '16px',
            padding: '16px',
            border: '2px solid #28a745',
            borderRadius: '8px',
            backgroundColor: '#d4edda',
          }}
        >
          <h4>Restore Complete</h4>
          <p>
            {state.summary.assets} assets, {state.summary.fuel_logs} fuel logs,{' '}
            {state.summary.maintenance_records} maintenance records, {state.summary.maintenance_schedules}{' '}
            maintenance schedules, {state.summary.attachments} attachment files restored.
            {state.summary.skipped_attachments > 0 &&
              ` ${state.summary.skipped_attachments} attachment(s) skipped (no file bundled in the backup, or a kind this platform can't link).`}
          </p>
        </div>
      )}

      {state.status === 'error' && (
        <p style={{ color: '#dc3545', marginTop: '12px' }}>{state.errorMessage}</p>
      )}
    </div>
  );
}
