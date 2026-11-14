// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { Navigate, Route, Routes } from "react-router-dom";
import { FEATURES } from "./app/features";
import { ForgotPasswordPage } from "./features/auth/ForgotPasswordPage";
import { LoginPage } from "./features/auth/LoginPage";
import { RegisterPage } from "./features/auth/RegisterPage";
import { ResetPasswordPage } from "./features/auth/ResetPasswordPage";
import { SetupGate } from "./features/auth/SetupGate";
import { JoinPage } from "./features/household/JoinPage";
import { Layout } from "./features/layout/Layout";
import { ProtectedRoute } from "./features/layout/ProtectedRoute";
import "./App.css";
import "./features/layout/shell.css";
import "./components/ui/ui.css";

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
          {/* The signed-in pages come from the feature registry
              (app/features.ts), the same list the menu is built from. */}
          {FEATURES.flatMap((feature) =>
            feature.routes.map((route) => <Route key={route.path} path={route.path} element={route.element} />),
          )}
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </SetupGate>
  );
}

export default App;
