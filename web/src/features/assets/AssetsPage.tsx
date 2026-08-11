import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { createAsset, listAssets } from "../../api/assets";
import type { AssetType } from "../../api/types";
import { ASSET_TYPES } from "./assetTypes";

export function AssetsPage() {
  const queryClient = useQueryClient();
  const { data: assets, isLoading } = useQuery({ queryKey: ["assets"], queryFn: listAssets });
  const [name, setName] = useState("");
  const [assetType, setAssetType] = useState<AssetType>("equipment");

  const createMutation = useMutation({
    mutationFn: () => createAsset({ asset_type: assetType, name }),
    onSuccess: () => {
      setName("");
      queryClient.invalidateQueries({ queryKey: ["assets"] });
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (name.trim()) createMutation.mutate();
  }

  return (
    <div>
      <h1>Assets</h1>
      <form className="inline-form" onSubmit={handleSubmit}>
        <select value={assetType} onChange={(e) => setAssetType(e.target.value as AssetType)}>
          {ASSET_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
        <input
          placeholder="Name (e.g. Family Minivan)"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button type="submit" disabled={createMutation.isPending}>
          Add asset
        </button>
      </form>

      {isLoading && <p>Loading…</p>}
      <ul className="asset-list">
        {assets?.map((asset) => (
          <li key={asset.id}>
            <Link to={`/assets/${asset.id}`}>
              <strong>{asset.name}</strong>
              <span className="asset-type">{ASSET_TYPES.find((t) => t.value === asset.asset_type)?.label}</span>
            </Link>
          </li>
        ))}
      </ul>
      {assets?.length === 0 && <p>No assets yet — add your first one above.</p>}
    </div>
  );
}
