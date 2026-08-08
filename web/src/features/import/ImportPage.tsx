import { useQuery, useQueryClient } from '@tanstack/react-query';
import { listAssets } from '../../api/assets';
import { FuellyImport } from './FuellyImport';

export function ImportPage() {
  const queryClient = useQueryClient();
  const { data: assets = [], isLoading } = useQuery({
    queryKey: ['assets'],
    queryFn: listAssets,
  });

  if (isLoading) {
    return <div style={{ padding: '20px' }}>Loading assets...</div>;
  }

  return (
    <div>
      <FuellyImport
        assets={assets}
        onAssetsCreated={() => queryClient.invalidateQueries({ queryKey: ['assets'] })}
      />
    </div>
  );
}
