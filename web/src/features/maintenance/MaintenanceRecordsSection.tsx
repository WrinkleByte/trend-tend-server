import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createMaintenanceRecord,
  deleteMaintenanceRecord,
  listMaintenanceRecords,
  updateMaintenanceRecord,
} from "../../api/maintenanceRecords";
import { listMaintenanceSchedules, updateMaintenanceSchedule } from "../../api/maintenanceSchedules";
import {
  categoriesForAssetType,
  categoryLabel,
  CUSTOM_CATEGORY_VALUE,
  recordMatchesSchedule,
} from "../schedules/maintenanceAlerts";
import type { MaintenanceRecord, MaintenanceSchedule } from "../../api/types";
import { uploadPendingAttachments } from "../../api/attachments";
import { AttachmentsSection } from "../attachments/AttachmentsSection";
import { PendingAttachmentPicker } from "../attachments/PendingAttachmentPicker";
import { GridField } from "../../components/GridField";

export function MaintenanceRecordsSection({ assetId, assetType }: { assetId: string; assetType: string }) {
  const CATEGORIES = categoriesForAssetType(assetType);
  const queryClient = useQueryClient();
  const { data: records, isLoading } = useQuery({
    queryKey: ["maintenance-records", assetId],
    queryFn: () => listMaintenanceRecords(assetId),
  });
  // Same query key MaintenanceAlertsSection.tsx uses -- shares its cache.
  // Needed here only to check for a matching active schedule right after a
  // record is created; the section itself has no schedule UI of its own.
  const { data: schedules } = useQuery({
    queryKey: ["maintenance-schedules", assetId],
    queryFn: () => listMaintenanceSchedules(assetId),
  });
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const [performedAt, setPerformedAt] = useState(() => new Date().toISOString().slice(0, 10));
  const [category, setCategory] = useState(CATEGORIES[0]);
  // Vikunja: multi-category tagging -- additive to `category` above, which
  // stays the single "primary" value. Comma-joined into additional_categories
  // on save. A custom name typed via "Add new category" goes straight into
  // this set as free text (no CUSTOM_CATEGORY_VALUE sentinel needed here,
  // unlike the primary category, since there's no single paired free-text
  // field -- any entry not in CATEGORIES is displayed and matched verbatim).
  const [additionalCategories, setAdditionalCategories] = useState<Set<string>>(new Set());
  const [newAdditionalCategoryName, setNewAdditionalCategoryName] = useState("");
  const [description, setDescription] = useState("");
  const [cost, setCost] = useState("");
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);

  function toggleAdditionalCategory(c: string) {
    setAdditionalCategories((prev) => {
      const next = new Set(prev);
      if (next.has(c)) next.delete(c);
      else next.add(c);
      return next;
    });
  }

  function toggleEditAdditionalCategory(c: string) {
    setEditAdditionalCategories((prev) => {
      const next = new Set(prev);
      if (next.has(c)) next.delete(c);
      else next.add(c);
      return next;
    });
  }

  // Edit-in-place state (Vikunja #111) -- only one row editable at a time.
  // Unlike the quick-add form above, this exposes every field the backend
  // tracks on a MaintenanceRecord (MaintenanceRecordUpdate schema) -- the
  // oil/fluid fields sync down from mobile, where they're the only place
  // currently editable, and had no web entry point at all before this.
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editPerformedAt, setEditPerformedAt] = useState("");
  const [editCategory, setEditCategory] = useState(CATEGORIES[0]);
  const [editCustomCategory, setEditCustomCategory] = useState("");
  const [editAdditionalCategories, setEditAdditionalCategories] = useState<Set<string>>(new Set());
  const [newEditAdditionalCategoryName, setNewEditAdditionalCategoryName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editCost, setEditCost] = useState("");
  const [editPerformedBy, setEditPerformedBy] = useState("");
  const [editOilViscosity, setEditOilViscosity] = useState("");
  const [editOilFormulation, setEditOilFormulation] = useState("");
  const [editOilMeetsDexos, setEditOilMeetsDexos] = useState(false);
  const [editFilterPartNumber, setEditFilterPartNumber] = useState("");
  const [editFluidType, setEditFluidType] = useState("");
  const [editCapacity, setEditCapacity] = useState("");

  function startEdit(record: MaintenanceRecord) {
    setEditingId(record.id);
    setEditPerformedAt(record.performed_at.slice(0, 10));
    setEditCategory(record.category);
    setEditCustomCategory(record.custom_category ?? "");
    setEditAdditionalCategories(
      new Set((record.additional_categories ?? "").split(",").map((c) => c.trim()).filter(Boolean)),
    );
    setEditDescription(record.description ?? "");
    setEditCost(record.cost ?? "");
    setEditPerformedBy(record.performed_by ?? "");
    setEditOilViscosity(record.oil_viscosity ?? "");
    setEditOilFormulation(record.oil_formulation ?? "");
    setEditOilMeetsDexos(record.oil_meets_dexos ?? false);
    setEditFilterPartNumber(record.filter_part_number ?? "");
    setEditFluidType(record.fluid_type ?? "");
    setEditCapacity(record.capacity ?? "");
  }

  const updateRecordMutation = useMutation({
    mutationFn: (id: string) =>
      updateMaintenanceRecord(id, {
        performed_at: editPerformedAt,
        category: editCategory,
        custom_category: editCategory === CUSTOM_CATEGORY_VALUE ? editCustomCategory || null : null,
        additional_categories:
          editAdditionalCategories.size > 0 ? Array.from(editAdditionalCategories).join(",") : null,
        description: editDescription || null,
        cost: editCost ? Number(editCost) : null,
        performed_by: editPerformedBy || null,
        // Nulled out (not just hidden) when the category no longer
        // matches -- otherwise a value left over from before the user
        // switched categories mid-edit would silently persist despite
        // the field no longer being shown at all. Mirrors the mobile
        // apps' save-time gating (MaintenanceRecordFormScreen.kt/
        // MaintenanceRecordFormView.swift), same category sets as the
        // conditional rendering above.
        oil_viscosity: editCategory === "oil_change" ? editOilViscosity || null : null,
        oil_formulation: editCategory === "oil_change" ? editOilFormulation || null : null,
        oil_meets_dexos: editCategory === "oil_change" ? editOilMeetsDexos : null,
        filter_part_number: ["oil_change", "air_filter", "transmission_fluid"].includes(editCategory)
          ? editFilterPartNumber || null
          : null,
        fluid_type: ["transmission_fluid", "coolant", "differential_front", "differential_rear"].includes(editCategory)
          ? editFluidType || null
          : null,
        capacity: ["oil_change", "transmission_fluid", "differential_front", "differential_rear"].includes(editCategory)
          ? editCapacity || null
          : null,
      }),
    onSuccess: () => {
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["maintenance-records", assetId] });
    },
  });

  function handleEditSubmit(event: FormEvent, id: string) {
    event.preventDefault();
    updateRecordMutation.mutate(id);
  }

  // Vikunja #110: after a manually-added record, check for an active
  // schedule whose name matches its category and offer to clear it too --
  // mirrors mobile's ScheduleMatchConfirmationView (getActiveSchedulesForCategorySync),
  // including its "list every match individually, default all selected"
  // handling of duplicate same-name schedules.
  const [pendingMatch, setPendingMatch] = useState<{
    record: MaintenanceRecord;
    schedules: MaintenanceSchedule[];
    selected: Set<string>;
  } | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      createMaintenanceRecord({
        asset_id: assetId,
        performed_at: performedAt,
        category,
        additional_categories: additionalCategories.size > 0 ? Array.from(additionalCategories).join(",") : null,
        description: description || null,
        cost: cost ? Number(cost) : null,
      }),
    onSuccess: (record) => {
      setDescription("");
      setCost("");
      setAdditionalCategories(new Set());
      if (pendingFiles.length > 0) {
        const files = pendingFiles;
        setPendingFiles([]);
        uploadPendingAttachments("record", record.id, files).then(() =>
          queryClient.invalidateQueries({ queryKey: ["attachments", "record", record.id] }),
        );
      }
      queryClient.invalidateQueries({ queryKey: ["maintenance-records", assetId] });

      const matches = (schedules ?? []).filter((s) => s.active && recordMatchesSchedule(record, s.name));
      if (matches.length > 0) {
        setPendingMatch({ record, schedules: matches, selected: new Set(matches.map((s) => s.id)) });
      }
    },
  });

  const clearMatchingSchedulesMutation = useMutation({
    mutationFn: async () => {
      if (!pendingMatch) return;
      const toClear = pendingMatch.schedules.filter((s) => pendingMatch.selected.has(s.id));
      await Promise.all(
        toClear.map((s) =>
          updateMaintenanceSchedule(s.id, {
            anchor_date: pendingMatch.record.performed_at,
            anchor_usage_value: pendingMatch.record.odometer_reading,
            dismissed_at: null,
          }),
        ),
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["maintenance-schedules", assetId] });
      setPendingMatch(null);
    },
  });

  function toggleMatchSelected(scheduleId: string) {
    setPendingMatch((prev) => {
      if (!prev) return prev;
      const selected = new Set(prev.selected);
      if (selected.has(scheduleId)) selected.delete(scheduleId);
      else selected.add(scheduleId);
      return { ...prev, selected };
    });
  }

  const deleteMutation = useMutation({
    mutationFn: (recordId: string) => deleteMaintenanceRecord(recordId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["maintenance-records", assetId] }),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate();
  }

  // Mirrors AssetDetailPage.tsx's confirm() guard (Vikunja #34) -- extended
  // to fuel/service/trip records per explicit follow-up request rather than
  // left as a latent gap like the other unguarded deletes in this app. This
  // is the exact entity type that prompted the follow-up (an accidental
  // single-click delete on this same section).
  function handleDelete(recordId: string, performedAt: string, category: string) {
    const label = categoryLabel(category);
    if (window.confirm(`Permanently delete this ${label} record from ${performedAt.slice(0, 10)}? This cannot be undone.`)) {
      deleteMutation.mutate(recordId);
    }
  }

  return (
    <section>
      <h2>Service history</h2>
      <form className="inline-form" onSubmit={handleSubmit}>
        <input type="date" value={performedAt} onChange={(e) => setPerformedAt(e.target.value)} required />
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {categoryLabel(c)}
            </option>
          ))}
        </select>
        <textarea
          placeholder="Description"
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <input
          type="number"
          step="0.01"
          placeholder="Cost"
          value={cost}
          onChange={(e) => setCost(e.target.value)}
        />
        <button type="submit" disabled={createMutation.isPending}>
          Add record
        </button>
      </form>
      <details className="additional-categories">
        <summary>
          Additional categories{additionalCategories.size > 0 ? ` (${additionalCategories.size})` : ""}
        </summary>
        <div className="additional-categories-list">
          {CATEGORIES.filter((c) => c !== CUSTOM_CATEGORY_VALUE).map((c) => (
            <label key={c}>
              <input
                type="checkbox"
                checked={additionalCategories.has(c)}
                onChange={() => toggleAdditionalCategory(c)}
              />
              {categoryLabel(c)}
            </label>
          ))}
          {/* Custom names already checked this session (typed via "Add"
              below) -- web has no remembered-custom-category list the way
              mobile does, so these only exist for the life of this form. */}
          {Array.from(additionalCategories)
            .filter((c) => !CATEGORIES.includes(c))
            .map((c) => (
              <label key={c}>
                <input
                  type="checkbox"
                  checked
                  onChange={() => toggleAdditionalCategory(c)}
                />
                {c}
              </label>
            ))}
        </div>
        <div className="additional-categories-add">
          <input
            placeholder="Add new category"
            value={newAdditionalCategoryName}
            onChange={(e) => setNewAdditionalCategoryName(e.target.value)}
          />
          <button
            type="button"
            disabled={!newAdditionalCategoryName.trim()}
            onClick={() => {
              const trimmed = newAdditionalCategoryName.trim();
              if (!trimmed) return;
              setAdditionalCategories((prev) => new Set(prev).add(trimmed));
              setNewAdditionalCategoryName("");
            }}
          >
            Add
          </button>
        </div>
      </details>
      <PendingAttachmentPicker files={pendingFiles} onFilesChange={setPendingFiles} />

      {pendingMatch && (
        <div className="schedule-match-prompt">
          <p>
            This matches {pendingMatch.schedules.length === 1 ? "an active reminder" : "active reminders"} for this
            asset. Clear it too?
          </p>
          <ul>
            {pendingMatch.schedules.map((s) => (
              <li key={s.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={pendingMatch.selected.has(s.id)}
                    onChange={() => toggleMatchSelected(s.id)}
                  />
                  {s.name}
                  {s.next_due_date ? ` (due ${s.next_due_date})` : ""}
                </label>
              </li>
            ))}
          </ul>
          <div className="schedule-match-actions">
            <button
              type="button"
              onClick={() => clearMatchingSchedulesMutation.mutate()}
              disabled={clearMatchingSchedulesMutation.isPending || pendingMatch.selected.size === 0}
            >
              Confirm
            </button>
            <button type="button" onClick={() => setPendingMatch(null)}>
              Skip
            </button>
          </div>
        </div>
      )}

      {isLoading && <p>Loading…</p>}
      <ul className="record-list">
        {records?.map((record) =>
          editingId === record.id ? (
            <li key={record.id}>
              <form className="record-edit-form" onSubmit={(e) => handleEditSubmit(e, record.id)}>
                <div className="field-grid field-compact">
                  <GridField
                    label="Date"
                    type="date"
                    value={editPerformedAt}
                    onChange={setEditPerformedAt}
                  />
                  <div className="form-field">
                    <label htmlFor="record-edit-category">Category</label>
                    <select
                      id="record-edit-category"
                      value={editCategory}
                      onChange={(e) => setEditCategory(e.target.value)}
                    >
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                          {categoryLabel(c)}
                        </option>
                      ))}
                    </select>
                  </div>
                  {editCategory === CUSTOM_CATEGORY_VALUE && (
                    <GridField label="Custom category" value={editCustomCategory} onChange={setEditCustomCategory} />
                  )}
                  <div className="field-full form-field">
                    <details className="additional-categories">
                      <summary>
                        Additional categories
                        {editAdditionalCategories.size > 0 ? ` (${editAdditionalCategories.size})` : ""}
                      </summary>
                      <div className="additional-categories-list">
                        {CATEGORIES.filter((c) => c !== CUSTOM_CATEGORY_VALUE).map((c) => (
                          <label key={c}>
                            <input
                              type="checkbox"
                              checked={editAdditionalCategories.has(c)}
                              onChange={() => toggleEditAdditionalCategory(c)}
                            />
                            {categoryLabel(c)}
                          </label>
                        ))}
                        {Array.from(editAdditionalCategories)
                          .filter((c) => !CATEGORIES.includes(c))
                          .map((c) => (
                            <label key={c}>
                              <input
                                type="checkbox"
                                checked
                                onChange={() => toggleEditAdditionalCategory(c)}
                              />
                              {c}
                            </label>
                          ))}
                      </div>
                      <div className="additional-categories-add">
                        <input
                          placeholder="Add new category"
                          value={newEditAdditionalCategoryName}
                          onChange={(e) => setNewEditAdditionalCategoryName(e.target.value)}
                        />
                        <button
                          type="button"
                          disabled={!newEditAdditionalCategoryName.trim()}
                          onClick={() => {
                            const trimmed = newEditAdditionalCategoryName.trim();
                            if (!trimmed) return;
                            setEditAdditionalCategories((prev) => new Set(prev).add(trimmed));
                            setNewEditAdditionalCategoryName("");
                          }}
                        >
                          Add
                        </button>
                      </div>
                    </details>
                  </div>
                  <div className="field-full form-field">
                    <label htmlFor="record-edit-description">Description</label>
                    <textarea
                      id="record-edit-description"
                      rows={3}
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                    />
                  </div>
                  <GridField label="Cost" type="number" step="0.01" value={editCost} onChange={setEditCost} />
                  <GridField label="Performed by" value={editPerformedBy} onChange={setEditPerformedBy} />
                  {/* Structured oil/fluid fields, meaningful only for
                      certain categories -- mirrors the exact category sets
                      the mobile apps gate these same fields on
                      (MaintenanceRecordFormScreen.kt/MaintenanceRecordFormView.swift).
                      Previously shown unconditionally regardless of
                      category, which is what prompted this. */}
                  {editCategory === "oil_change" && (
                    <>
                      <GridField label="Oil viscosity" placeholder="e.g. 5W-30" value={editOilViscosity} onChange={setEditOilViscosity} />
                      <GridField label="Oil formulation" placeholder="e.g. Synthetic" value={editOilFormulation} onChange={setEditOilFormulation} />
                    </>
                  )}
                  {["oil_change", "air_filter", "transmission_fluid"].includes(editCategory) && (
                    <GridField label="Filter part number" value={editFilterPartNumber} onChange={setEditFilterPartNumber} />
                  )}
                  {["transmission_fluid", "coolant", "differential_front", "differential_rear"].includes(editCategory) && (
                    <GridField label="Fluid type" value={editFluidType} onChange={setEditFluidType} />
                  )}
                  {["oil_change", "transmission_fluid", "differential_front", "differential_rear"].includes(editCategory) && (
                    <GridField label="Capacity" placeholder="e.g. 5 qt" value={editCapacity} onChange={setEditCapacity} />
                  )}
                  {editCategory === "oil_change" && (
                    <label className="check-label">
                      <input
                        type="checkbox"
                        checked={editOilMeetsDexos}
                        onChange={(e) => setEditOilMeetsDexos(e.target.checked)}
                      />
                      Meets dexos spec
                    </label>
                  )}
                </div>
                <div className="form-actions" style={{ marginTop: 12 }}>
                  <button type="submit" disabled={updateRecordMutation.isPending}>
                    Save
                  </button>
                  <button type="button" className="secondary" onClick={() => setEditingId(null)}>
                    Cancel
                  </button>
                </div>
              </form>
            </li>
          ) : (
            <li key={record.id}>
              <div className="record-row">
                <span className="record-date">{record.performed_at}</span>
                <span className="record-category">{categoryLabel(record.category)}</span>
                <span className="record-description">{record.description || "—"}</span>
                <span className="record-cost">{record.cost != null ? `$${record.cost}` : ""}</span>
                <div className="record-actions">
                  <button type="button" onClick={() => setExpandedId(expandedId === record.id ? null : record.id)}>
                    {expandedId === record.id ? "Hide photos" : "Photos"}
                  </button>
                  <button type="button" onClick={() => startEdit(record)}>
                    Edit
                  </button>
                  <button
                    type="button"
                    className="danger"
                    onClick={() => handleDelete(record.id, record.performed_at, record.category)}
                  >
                    Delete
                  </button>
                </div>
              </div>
              {expandedId === record.id && <AttachmentsSection entityType="record" entityId={record.id} />}
            </li>
          ),
        )}
      </ul>
      {records?.length === 0 && <p>No service history yet.</p>}
    </section>
  );
}
