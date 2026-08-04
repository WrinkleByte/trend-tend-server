import { Navigate, Route, Routes } from "react-router-dom";
import { AssetDetailPage } from "./features/assets/AssetDetailPage";
import { AssetsPage } from "./features/assets/AssetsPage";
import { LoginPage } from "./features/auth/LoginPage";
import { RegisterPage } from "./features/auth/RegisterPage";
import { HouseholdPage } from "./features/household/HouseholdPage";
import { JoinPage } from "./features/household/JoinPage";
import { Layout } from "./features/layout/Layout";
import { ProtectedRoute } from "./features/layout/ProtectedRoute";
import { ApiTokensPage } from "./features/settings/ApiTokensPage";
import "./App.css";

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
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
        <Route path="/settings" element={<ApiTokensPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
