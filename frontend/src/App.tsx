import { Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Login from "./pages/Login";
import CostCenters from "./pages/CostCenters";
import GLAccounts from "./pages/GLAccounts";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<ProtectedRoute><Home /></ProtectedRoute>} />
      <Route
        path="/cost-centers"
        element={<ProtectedRoute><Layout><CostCenters /></Layout></ProtectedRoute>}
      />
      <Route
        path="/gl-accounts"
        element={<ProtectedRoute><Layout><GLAccounts /></Layout></ProtectedRoute>}
      />
    </Routes>
  );
}
