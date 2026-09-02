import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Dashboard from "./pages/Dashboard";
import Setup from "./pages/Setup";
import Interview from "./pages/Interview";
import Report from "./pages/Report";
import ProtectedRoute from "./components/ProtectedRoute";

const PROTECTED_ROUTES = [
  { path: "/dashboard", element: <Dashboard /> },
  { path: "/setup", element: <Setup /> },
  { path: "/interview", element: <Interview /> },
  { path: "/report", element: <Report /> },
];

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        {PROTECTED_ROUTES.map(({ path, element }) => (
          <Route key={path} path={path} element={<ProtectedRoute>{element}</ProtectedRoute>} />
        ))}
      </Routes>
    </BrowserRouter>
  );
}
