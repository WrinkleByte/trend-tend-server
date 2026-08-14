import { useQuery, useQueryClient } from '@tanstack/react-query';
import { listAssets } from '../../api/assets';
import { AcarImport } from './AcarImport';
import { FuellyImport } from './FuellyImport';
import { RestoreBackup } from './RestoreBackup';

function invalidateAllHouseholdData(queryClient: ReturnType<typeof useQueryClient>) {
  // A restore can create assets plus maintenance records/schedules for
  // brand-new asset ids this component never sees -- broader than
  // FuellyImport's own onAssetsCreated (assets only). ["maintenance-records"]
  // and ["maintenance-schedules"] (no second key element) partial-match
  // every per-asset-scoped query for those, regardless of assetId. Fuel logs
  // have no queryable list view on web today (created via Fuelly import,
  // read only via Export) -- nothing to invalidate for them.
  queryClient.invalidateQueries({ queryKey: ['assets'] });
  queryClient.invalidateQueries({ queryKey: ['maintenance-records'] });
  queryClient.invalidateQueries({ queryKey: ['maintenance-schedules'] });
}

export function ImportPage() {
  const queryClient = useQueryClient();
  const { data: assets = [], isLoading } = useQuery({
    queryKey: ['assets'],
    queryFn: listAssets,
  });

  if (isLoading) {
    return (
      <div className="page-narrow">
        <p>Loading assets…</p>
      </div>
    );
  }

  return (
    <div className="page-narrow">
      <h1>Import</h1>
      <RestoreBackup onRestored={() => invalidateAllHouseholdData(queryClient)} />
      <FuellyImport
        assets={assets}
        onAssetsCreated={() => queryClient.invalidateQueries({ queryKey: ['assets'] })}
      />
      <AcarImport
        assets={assets}
        onAssetsCreated={() => queryClient.invalidateQueries({ queryKey: ['assets'] })}
      />
    </div>
  );
}
