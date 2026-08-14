import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listAllHouseholds, promoteUserToInstanceAdmin } from "../../api/admin";

function formatCounts(counts: {
  assets: number;
  fuel_logs: number;
  trip_logs: number;
  maintenance_records: number;
  maintenance_schedules: number;
}): string {
  return [
    `${counts.assets} asset${counts.assets === 1 ? "" : "s"}`,
    `${counts.fuel_logs} fuel log${counts.fuel_logs === 1 ? "" : "s"}`,
    `${counts.trip_logs} trip log${counts.trip_logs === 1 ? "" : "s"}`,
    `${counts.maintenance_records} maintenance record${counts.maintenance_records === 1 ? "" : "s"}`,
    `${counts.maintenance_schedules} schedule${counts.maintenance_schedules === 1 ? "" : "s"}`,
  ].join(" · ");
}

/**
 * Cross-household view — only ever visible to the instance admin, same
 * 403-renders-null gating as InstanceSettingsSection. Every other list
 * page in the app is scoped to the caller's own household; this is the
 * one deliberate exception.
 */
export function AdminHouseholdsSection() {
  const queryClient = useQueryClient();
  const { data: households, isError } = useQuery({
    queryKey: ["admin-households"],
    queryFn: listAllHouseholds,
    retry: false,
  });

  const promoteMutation = useMutation({
    mutationFn: (userId: string) => promoteUserToInstanceAdmin(userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-households"] }),
  });

  if (isError || !households) return null;

  return (
    <section className="panel">
      <span className="panel-eyebrow">Instance admin</span>
      <h2>All households</h2>
      <p>
        Every household on this instance, who belongs to each, and how much data they hold. Promoting a member
        gives them this same instance-wide access, including SMTP config and this household list.
      </p>

      <ul className="admin-household-list">
        {households.map((household) => (
          <li key={household.id}>
            <div className="admin-household-header">
              <strong>{household.name}</strong>
              <span className="admin-household-counts">{formatCounts(household.record_counts)}</span>
            </div>
            <ul className="admin-member-list">
              {household.members.map((member) => (
                <li key={member.user_id}>
                  <span>{member.display_name}</span>
                  <span className="member-email">{member.email}</span>
                  <span className="member-role">{member.role}</span>
                  {member.is_instance_admin ? (
                    <span className="panel-eyebrow">Admin</span>
                  ) : (
                    <button
                      type="button"
                      className="secondary"
                      disabled={promoteMutation.isPending}
                      onClick={() => promoteMutation.mutate(member.user_id)}
                    >
                      Promote to admin
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </section>
  );
}
