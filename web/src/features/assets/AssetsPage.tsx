import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { createAsset, listAssets } from "../../api/assets";
import type { Asset, AssetType } from "../../api/types";
import { useHouseholdMembers } from "../household/useHouseholdMembers";
import { ASSET_TYPES } from "./assetTypes";

// Remembered per browser so the choice survives a reload — it's a view
// preference, not shared state, so it deliberately doesn't go to the server.
const MINE_ONLY_KEY = "wrinklebyte.assets.mineOnly";

function readMineOnly(): boolean {
  try {
    return localStorage.getItem(MINE_ONLY_KEY) === "true";
  } catch {
    // Private windows and "block site data" both throw on access rather than
    // returning null. Showing everything is the right default when we can't
    // remember the preference.
    return false;
  }
}

// Tabs group by the same "main category" split the mobile apps' Home
// screen uses (property/home_system share one tab) -- see
// AssetListScreen.kt/AssetListView.swift's identical typeFilter grouping.
// "all" is included but deliberately not the default tab (below) -- most
// households have far more vehicles than anything else, so that's the
// more useful landing view.
const CATEGORY_TABS: { key: string; label: string }[] = [
  { key: "vehicle", label: "Vehicles" },
  { key: "equipment", label: "Equipment" },
  { key: "property", label: "Property" },
  { key: "valuable", label: "Valuables" },
  { key: "all", label: "All" },
];
const DEFAULT_CATEGORY = "vehicle";

function matchesCategory(asset: Asset, category: string): boolean {
  if (category === "all") return true;
  if (category === "property") return asset.asset_type === "property" || asset.asset_type === "home_system";
  return asset.asset_type === category;
}

export function AssetsPage() {
  const queryClient = useQueryClient();
  const [mineOnly, setMineOnly] = useState(readMineOnly);
  // Filtered server-side rather than by comparing owner_user_id here, so the
  // "mine, plus anything unassigned" rule lives in exactly one place (the
  // backend's list_assets) instead of drifting between client and server.
  const { data: assets, isLoading } = useQuery({
    queryKey: ["assets", { mineOnly }],
    queryFn: () => listAssets(mineOnly),
  });
  const { members, nameFor } = useHouseholdMembers();
  const [ownerUserId, setOwnerUserId] = useState("");
  const [searchParams, setSearchParams] = useSearchParams();
  const activeCategory = searchParams.get("category") ?? DEFAULT_CATEGORY;
  const [name, setName] = useState("");
  const [assetType, setAssetType] = useState<AssetType>("equipment");

  // Keeps the create form's Type picker pointed at whichever tab you're
  // looking at (e.g. on the Valuables tab, "Add asset" defaults to
  // creating a Valuable) rather than always defaulting to "equipment"
  // regardless of context. Only applies when the tab implies one real
  // type -- the "All" tab has no single implied type, so the picker's
  // current choice is left alone there.
  useEffect(() => {
    if (activeCategory !== "all" && activeCategory !== "property") {
      setAssetType(activeCategory as AssetType);
    }
  }, [activeCategory]);

  const createMutation = useMutation({
    mutationFn: () =>
      createAsset({ asset_type: assetType, name, owner_user_id: ownerUserId || null }),
    onSuccess: () => {
      setName("");
      queryClient.invalidateQueries({ queryKey: ["assets"] });
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (name.trim()) createMutation.mutate();
  }

  const categoryAssets = (assets ?? []).filter((a) => matchesCategory(a, activeCategory));
  const activeAssets = categoryAssets.filter((a) => a.status === "active");
  const retiredAssets = categoryAssets.filter((a) => a.status === "archived" || a.status === "disposed");

  return (
    <div>
      <h1>Assets</h1>

      <div className="asset-category-tabs" role="tablist" aria-label="Filter by asset type">
        {CATEGORY_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={activeCategory === tab.key}
            className={activeCategory === tab.key ? "asset-category-tab active" : "asset-category-tab"}
            onClick={() => setSearchParams(tab.key === DEFAULT_CATEGORY ? {} : { category: tab.key })}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Only worth offering once there's more than one person to distinguish
          — in a single-member household every asset is trivially "mine". */}
      {(members?.length ?? 0) > 1 && (
        <label className="check-label">
          <input
            type="checkbox"
            checked={mineOnly}
            onChange={(e) => {
              setMineOnly(e.target.checked);
              try {
                localStorage.setItem(MINE_ONLY_KEY, String(e.target.checked));
              } catch {
                // Preference just won't persist; the filter still applies now.
              }
            }}
          />
          Only show my stuff
        </label>
      )}
      {/* Outside the label, not inside it: .check-label lays its children out
          in a row, which would strand this sentence beside the checkbox. */}
      {(members?.length ?? 0) > 1 && (
        <p className="field-hint">
          Hides assets owned by other members. Unassigned assets always show.
        </p>
      )}

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
        {(members?.length ?? 0) > 1 && (
          <select
            value={ownerUserId}
            onChange={(e) => setOwnerUserId(e.target.value)}
            aria-label="Owner"
          >
            <option value="">Unassigned</option>
            {members?.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.display_name}
              </option>
            ))}
          </select>
        )}
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
              {asset.owner_user_id && (members?.length ?? 0) > 1 && (
                <span className="asset-owner">{nameFor(asset.owner_user_id)}</span>
              )}
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

      {!isLoading && categoryAssets.length === 0 && (
        <p>
          {activeCategory === "all"
            ? "No assets yet — add your first one above."
            : "No assets in this category yet — add one above, or check another tab."}
        </p>
      )}
    </div>
  );
}
