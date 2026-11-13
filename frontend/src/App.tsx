import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './features/auth/AuthContext';
import LoginPage from './features/auth/LoginPage';
import DashboardPage from './app/DashboardPage';
import PublicInvoicePage from './features/public-invoice/PublicInvoicePage';
import { ProtectedRoute } from './features/auth/ProtectedRoute';
import { AppLayout } from './app/AppLayout';
import { RoomListPage } from './features/rooms/RoomListPage';
import { TenantListPage } from './features/tenants/TenantListPage';
import { ContractListPage } from './features/contracts/ContractListPage';
import { ContractDetailPage } from './features/contracts/ContractDetailPage';
import { ContractWizardPage } from './features/contracts/ContractWizardPage';
import { PropertyListPage } from './features/properties/PropertyListPage';
import { MeterListPage } from './features/meters/MeterListPage';
import { InvoiceListPage } from './features/invoices/InvoiceListPage';
import { InvoiceDetailPage } from './features/invoices/InvoiceDetailPage';
import { EmailListPage } from './features/notifications/EmailListPage';

export default function App() {
  const { user, loading } = useAuth();

  if (loading) return <div className="boot-loader">Đang khởi động…</div>;

  return (
    <Routes>
      <Route path="/dang-nhap" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/cau-truc" element={<PropertyListPage />} />
          <Route path="/phong" element={<RoomListPage />} />
          <Route path="/nguoi-thue" element={<TenantListPage />} />
          <Route path="/hop-dong" element={<ContractListPage />} />
          <Route path="/hop-dong/tao-moi" element={<ContractWizardPage />} />
          <Route path="/hop-dong/:id" element={<ContractDetailPage />} />
          <Route path="/dong-ho" element={<MeterListPage />} />
          <Route path="/hoa-don" element={<InvoiceListPage />} />
          <Route path="/hoa-don/:id" element={<InvoiceDetailPage />} />
          <Route path="/email" element={<EmailListPage />} />
        </Route>
      </Route>
      <Route path="/hoa-don-cong-khai/:token" element={<PublicInvoicePage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}