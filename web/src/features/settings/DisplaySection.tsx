import { useAssetPhotosEnabled } from "./assetPhotosSetting";
import { useThemePreference, type ThemePreference } from "./themeSetting";

/** Per-device display preferences — theme ("skin choice") and the asset
 * profile-photo visibility toggle. Split out of the old single-page
 * ApiTokensPage as its own "Display" settings category. */
export function DisplaySection() {
  const [assetPhotosEnabled, setAssetPhotosEnabled] = useAssetPhotosEnabled();
  const [theme, setTheme] = useThemePreference();

  return (
    <section className="panel">
      <h2>Display</h2>
      <label style={{ maxWidth: "200px", marginBottom: "16px" }}>
        Theme
        <select value={theme} onChange={(e) => setTheme(e.target.value as ThemePreference)}>
          <option value="system">Match system</option>
          <option value="light">Light</option>
          <option value="dark">Dark</option>
        </select>
      </label>
      <label className="check-label" style={{ marginBottom: 0 }}>
        <input type="checkbox" checked={assetPhotosEnabled} onChange={(e) => setAssetPhotosEnabled(e.target.checked)} />
        Show asset profile photos
      </label>
    </section>
  );
}
