// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { Navigate, useParams } from "react-router-dom";
import { PageHeader } from "../../components/ui/PageHeader";
import { TabNav } from "../../components/ui/TabNav";
import { ExportPage } from "../export/ExportPage";
import { ImportPage } from "../import/ImportPage";

/** Import and export are occasional jobs, so they share one menu entry
 * instead of taking two slots in the main navigation. */
export function DataPage() {
  const { tab } = useParams<{ tab: string }>();
  if (tab !== "import" && tab !== "export") return <Navigate to="/data/export" replace />;
  return (
    <div>
      <PageHeader title="Import & export" subtitle="Back up your household, or bring records in from another app." />
      <TabNav
        label="Import or export"
        items={[
          { to: "/data/export", label: "Export" },
          { to: "/data/import", label: "Import" },
        ]}
      />
      {tab === "import" ? <ImportPage /> : <ExportPage />}
    </div>
  );
}
