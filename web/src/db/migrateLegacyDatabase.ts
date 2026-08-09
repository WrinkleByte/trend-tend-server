import Dexie from "dexie";
import { db } from "./db";
import { V1_STORES } from "./schema";

const LEGACY_DB_NAME = "tendfida";
const MIGRATION_FLAG_KEY = "wrinklebyte-db-migrated";

/**
 * One-time carry-forward of the pre-rename "tendfida" IndexedDB database
 * into the renamed "wrinklebyte" one, for browsers with an existing
 * installed PWA from before the WrinkleByte rebrand. Dexie has no built-in
 * database rename, and simply changing the name string in schema.ts would
 * otherwise be indistinguishable from a fresh install with no local data.
 *
 * Must run (and be awaited) before anything touches the app's `db`
 * singleton for real — call this at the top of the app's bootstrap, before
 * rendering, so no component can query `db` until migration has settled.
 */
export async function migrateLegacyDatabase(): Promise<void> {
  if (localStorage.getItem(MIGRATION_FLAG_KEY)) return;

  const legacyExists = await Dexie.exists(LEGACY_DB_NAME);
  if (!legacyExists) {
    // Fresh install (or already-renamed-and-cleaned-up device) — nothing
    // to carry forward.
    localStorage.setItem(MIGRATION_FLAG_KEY, "true");
    return;
  }

  const legacyDb = new Dexie(LEGACY_DB_NAME);
  legacyDb.version(1).stores(V1_STORES);

  try {
    await legacyDb.open();
    for (const table of Object.keys(V1_STORES) as (keyof typeof V1_STORES)[]) {
      const rows = await legacyDb.table(table).toArray();
      if (rows.length > 0) {
        await db.table(table).bulkPut(rows);
      }
    }
    legacyDb.close();
    // Only delete the legacy database once every table above has copied
    // successfully — if anything threw before this point, the legacy data
    // is still intact and untouched for a retry on the next app load.
    await legacyDb.delete();
    localStorage.setItem(MIGRATION_FLAG_KEY, "true");
  } catch (err) {
    console.error(
      "Legacy 'tendfida' database migration failed — will retry on next app load:",
      err,
    );
    legacyDb.close();
  }
}
