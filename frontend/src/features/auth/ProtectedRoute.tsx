import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from './AuthContext';

export function ProtectedRoute() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/dang-nhap" replace />;
  return <Outlet />;
}