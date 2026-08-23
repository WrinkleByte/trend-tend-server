import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { deleteHousehold, getCurrentHousehold, wipeHouseholdData } from "../../api/households";
import { useAuthStore } from "../../auth/authStore";
import { StatusMessage } from "../../components/StatusMessage";

/** Owner-only "wipe all data" / "delete household" -- moved here from
 * HouseholdPage.tsx (Vikunja #105) so these two irreversible, easy-to-fat-
 * finger actions live in their own dedicated Settings category instead of
 * at the bottom of the regular household page, mirroring the same
 * consolidation the mobile apps' HouseholdDangerZoneView/Screen already
 * do. Self-hides for a non-owner exactly like it did on HouseholdPage,
 * same pattern InstanceSettingsSection uses for its own 403 case. */
export function DangerZoneSection() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const clearAuth = useAuthStore((s) => s.clear);
  const { data: household } = useQuery({ queryKey: ["household"], queryFn: getCurrentHousehold });
  const isOwner = household?.my_role === "owner";

  const [confirmDeleteText, setConfirmDeleteText] = useState("");
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [confirmWipeText, setConfirmWipeText] = useState("");
  const [wipeAcknowledged, setWipeAcknowledged] = useState(false);
  const [confirmingWipe, setConfirmingWipe] = useState(false);
  const [wiped, setWiped] = useState(false);

  const deleteHouseholdMutation = useMutation({
    mutationFn: () => deleteHousehold(),
    onSuccess: () => {
      // Every member's session for this household is invalid the moment
      // it's gone, including the owner's who just deleted it — there's no
      // "switch to another household" here, just a clean logout. Anyone
      // with a membership elsewhere just logs back in normally.
      clearAuth();
      navigate("/login");
    },
  });

  const wipeHouseholdMutation = useMutation({
    mutationFn: () => wipeHouseholdData(),
    onSuccess: () => {
      // Unlike delete, the session and household survive — just refetch
      // everything asset-scoped so stale cached data doesn't linger on
      // whatever page the owner navigates to next. The 1-element key
      // prefixes below partial-match every per-asset-scoped query
      // regardless of asset id, same pattern ImportPage's restore-invalidation
      // already relies on.
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      queryClient.invalidateQueries({ queryKey: ["maintenance-records"] });
      queryClient.invalidateQueries({ queryKey: ["maintenance-schedules"] });
      queryClient.invalidateQueries({ queryKey: ["trip-logs"] });
      queryClient.invalidateQueries({ queryKey: ["fuel-logs"] });
      setConfirmingWipe(false);
      setConfirmWipeText("");
      setWipeAcknowledged(false);
      setWiped(true);
    },
  });

  if (!isOwner || !household) {
    return <p>Only the household owner can wipe data or delete the household.</p>;
  }

  return (
    <section className="panel panel-danger">
      <h2>Danger zone</h2>
      <p style={{ opacity: 0.75 }}>
        These actions affect <strong>{household.name}</strong> on the server — every device and member synced to
        it, not just this browser.
      </p>

      <h3>Wipe all data</h3>
      {wiped && !confirmingWipe && (
        <p className="notice notice-success">
          All data has been wiped. {household.name} still exists — assets, logs, and records just start empty
          again.
        </p>
      )}
      {!confirmingWipe ? (
        <button type="button" className="danger" onClick={() => setConfirmingWipe(true)}>
          Wipe all data
        </button>
      ) : (
        <div className="notice notice-error">
          <p>
            This permanently deletes every asset, service record, schedule, fuel log, trip log, and photo in{" "}
            <strong>{household.name}</strong>. The household itself, its members, and their logins are
            <strong> not</strong> affected — this is for starting over, not leaving. This cannot be undone.
          </p>
          <label style={{ marginTop: "12px" }}>
            Type <strong>{household.name}</strong> to confirm
            <input value={confirmWipeText} onChange={(e) => setConfirmWipeText(e.target.value)} />
          </label>
          <label className="check-label" style={{ marginTop: "12px" }}>
            <input
              type="checkbox"
              checked={wipeAcknowledged}
              onChange={(e) => setWipeAcknowledged(e.target.checked)}
            />
            I understand every asset and record will be permanently deleted and this cannot be undone
          </label>
          {wipeHouseholdMutation.isError && <StatusMessage>Something went wrong — no data was wiped.</StatusMessage>}
          <div className="form-actions" style={{ marginTop: "12px" }}>
            <button
              type="button"
              className="danger"
              disabled={confirmWipeText !== household.name || !wipeAcknowledged || wipeHouseholdMutation.isPending}
              onClick={() => wipeHouseholdMutation.mutate()}
            >
              {wipeHouseholdMutation.isPending ? "Wiping…" : "Permanently wipe all data"}
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setConfirmingWipe(false);
                setConfirmWipeText("");
                setWipeAcknowledged(false);
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <h3 style={{ marginTop: "24px" }}>Delete household</h3>
      {!confirmingDelete ? (
        <button type="button" className="danger" onClick={() => setConfirmingDelete(true)}>
          Delete household
        </button>
      ) : (
        <div className="notice notice-error">
          <p>
            This permanently deletes <strong>{household.name}</strong> — every asset, service record, fuel and
            trip log, schedule, and member. Every other member (including any co-owners) loses access immediately.
            This cannot be undone.
          </p>
          <label style={{ marginTop: "12px" }}>
            Type <strong>{household.name}</strong> to confirm
            <input value={confirmDeleteText} onChange={(e) => setConfirmDeleteText(e.target.value)} />
          </label>
          {deleteHouseholdMutation.isError && (
            <StatusMessage>Something went wrong — the household was not deleted.</StatusMessage>
          )}
          <div className="form-actions" style={{ marginTop: "12px" }}>
            <button
              type="button"
              className="danger"
              disabled={confirmDeleteText !== household.name || deleteHouseholdMutation.isPending}
              onClick={() => deleteHouseholdMutation.mutate()}
            >
              {deleteHouseholdMutation.isPending ? "Deleting…" : "Permanently delete household"}
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setConfirmingDelete(false);
                setConfirmDeleteText("");
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
