import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createMaintenanceRecord,
  deleteMaintenanceRecord,
  listMaintenanceRecords,
} from "../../api/maintenanceRecords";
import { AttachmentsSection } from "../attachments/AttachmentsSection";

const CATEGORIES = ["oil_change", "tires", "repair", "inspection", "cleaning", "filter", "other"];

export function MaintenanceRecordsSection({ assetId }: { assetId: string }) {
  const queryClient = useQueryClient();
  const { data: records, isLoading } = useQuery({
    queryKey: ["maintenance-records", assetId],
    queryFn: () => listMaintenanceRecords(assetId),
  });
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const [performedAt, setPerformedAt] = useState(() => new Date().toISOString().slice(0, 10));
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [description, setDescription] = useState("");
  const [cost, setCost] = useState("");

  const createMutation = useMutation({
    mutationFn: () =>
      createMaintenanceRecord({
        asset_id: assetId,
        performed_at: performedAt,
        category,
        description: description || null,
        cost: cost ? Number(cost) : null,
      }),
    onSuccess: () => {
      setDescription("");
      setCost("");
      queryClient.invalidateQueries({ queryKey: ["maintenance-records", assetId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (recordId: string) => deleteMaintenanceRecord(recordId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["maintenance-records", assetId] }),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate();
  }

  return (
    <section>
      <h2>Service history</h2>
      <form className="inline-form" onSubmit={handleSubmit}>
        <input type="date" value={performedAt} onChange={(e) => setPerformedAt(e.target.value)} required />
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c.replace("_", " ")}
            </option>
          ))}
        </select>
        <input placeholder="Description" value={description} onChange={(e) => setDescription(e.target.value)} />
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

      {isLoading && <p>Loading…</p>}
      <ul className="record-list">
        {records?.map((record) => (
          <li key={record.id}>
            <div className="record-row">
              <span className="record-date">{record.performed_at}</span>
              <span className="record-category">{record.category.replace("_", " ")}</span>
              <span className="record-description">{record.description}</span>
              <span className="record-cost">{record.cost != null ? `$${record.cost}` : ""}</span>
              <button type="button" onClick={() => setExpandedId(expandedId === record.id ? null : record.id)}>
                {expandedId === record.id ? "Hide receipts" : "Receipts"}
              </button>
              <button type="button" className="danger" onClick={() => deleteMutation.mutate(record.id)}>
                Delete
              </button>
            </div>
            {expandedId === record.id && <AttachmentsSection recordId={record.id} />}
          </li>
        ))}
      </ul>
      {records?.length === 0 && <p>No service history yet.</p>}
    </section>
  );
}
