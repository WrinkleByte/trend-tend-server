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

  const activeAssets = assets?.filter((a) => a.status === "active") ?? [];
  const retiredAssets = assets?.filter((a) => a.status === "archived" || a.status === "disposed") ?? [];

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

      {/* Active/Retired split mirrors the mobile apps' AssetListScreen.kt/
          AssetListView.swift grouping (Vikunja #106) -- a retired asset used
          to sit interleaved alphabetically among active ones here with no
          visual distinction beyond a status pill you'd only see after
          clicking in. */}
      <ul className="asset-list">
        {activeAssets.map((asset) => (
          <li key={asset.id}>
            <Link to={`/assets/${asset.id}`}>
              <strong>{asset.name}</strong>
              <span className="asset-type">{ASSET_TYPES.find((t) => t.value === asset.asset_type)?.label}</span>
            </Link>
          </li>
        ))}
      </ul>

      {retiredAssets.length > 0 && (
        <>
          <h2 className="asset-list-section-heading">Retired</h2>
          <ul className="asset-list asset-list-retired">
            {retiredAssets.map((asset) => (
              <li key={asset.id}>
                <Link to={`/assets/${asset.id}`}>
                  <strong>{asset.name}</strong>
                  <span className="asset-type">{ASSET_TYPES.find((t) => t.value === asset.asset_type)?.label}</span>
                  <span className={`status-pill status-${asset.status}`}>{asset.status}</span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}

      {assets?.length === 0 && <p>No assets yet — add your first one above.</p>}
    </div>
  );
}
