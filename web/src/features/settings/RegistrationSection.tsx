import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getInstanceSettings, updateInstanceSettings } from "../../api/instanceSettings";
import { StatusMessage } from "../../components/StatusMessage";

/**
 * Instance-admin control over whether strangers can create their own account.
 *
 * Shares the ["instance-settings"] query with InstanceSettingsSection (SMTP)
 * rather than fetching its own copy, and follows the same convention as every
 * other admin section: render null on a 403 instead of an error, because "not
 * the instance admin" is the ordinary case for most logged-in users.
 *
 * Saves immediately on toggle — it's a single boolean with no other fields to
 * batch it with, so a Save button would only add a step.
 */
export function RegistrationSection() {
  const queryClient = useQueryClient();
  const { data: settings, isError } = useQuery({
    queryKey: ["instance-settings"],
    queryFn: getInstanceSettings,
    retry: false,
  });

  const saveMutation = useMutation({
    mutationFn: (allow: boolean) => updateInstanceSettings({ allow_self_registration: allow }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["instance-settings"], updated);
      // The login/register pages gate on this flag via a staleTime:Infinity
      // query, so without this they'd keep offering signup for the rest of
      // the session after an admin closed it.
      queryClient.invalidateQueries({ queryKey: ["setup-status"] });
    },
  });

  if (isError || !settings) return null;

  return (
    <section className="panel">
      <span className="panel-eyebrow">Instance admin</span>
      <h2>Registration</h2>
      <p>
        Controls whether anyone who can reach this instance may create their own account and
        household from the login page.
      </p>
      <label className="check-label">
        <input
          type="checkbox"
          checked={settings.allow_self_registration}
          disabled={saveMutation.isPending}
          onChange={(e) => saveMutation.mutate(e.target.checked)}
        />
        Allow self-service registration
      </label>
      <p className="field-hint">
        Turning this off hides the &ldquo;Register&rdquo; link and rejects new signups. Household
        owners can still invite people, and anyone holding a valid invite link can still create
        their account &mdash; closing registration never blocks an invited user.
      </p>
      {saveMutation.isError && <StatusMessage>Couldn&rsquo;t save that — try again.</StatusMessage>}
    </section>
  );
}
