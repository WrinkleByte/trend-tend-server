import { Navigate, Route, Routes } from "react-router-dom";
import { AssetDetailPageNewView as AssetDetailPage } from "./features/assets/AssetDetailPage.NewView";
import { AssetsPage } from "./features/assets/AssetsPage";
import { ForgotPasswordPage } from "./features/auth/ForgotPasswordPage";
import { LoginPage } from "./features/auth/LoginPage";
import { RegisterPage } from "./features/auth/RegisterPage";
import { ResetPasswordPage } from "./features/auth/ResetPasswordPage";
import { SetupGate } from "./features/auth/SetupGate";
import { ExportPage } from "./features/export/ExportPage";
import { HouseholdPage } from "./features/household/HouseholdPage";
import { JoinPage } from "./features/household/JoinPage";
import { ImportPage } from "./features/import/ImportPage";
import { Layout } from "./features/layout/Layout";
import { ProtectedRoute } from "./features/layout/ProtectedRoute";
import { ApiTokensPage } from "./features/settings/ApiTokensPage";
import "./App.css";

function App() {
  return (
    <SetupGate>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        {/* Public: reachable whether or not the visitor already has an account. */}
        <Route path="/join" element={<JoinPage />} />
        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<AssetsPage />} />
          <Route path="/assets/:id" element={<AssetDetailPage />} />
          <Route path="/household" element={<HouseholdPage />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="/export" element={<ExportPage />} />
          <Route path="/settings" element={<ApiTokensPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </SetupGate>
  );
}

export default App;
