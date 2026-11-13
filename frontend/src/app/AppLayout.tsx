import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../features/auth/AuthContext';
import '../styles/layout.css';

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const navItems = [
    { path: '/', label: 'Sân vườn' },
    { path: '/cau-truc', label: 'Khu trọ' },
    { path: '/phong', label: 'Phòng' },
    { path: '/nguoi-thue', label: 'Người thuê' },
    { path: '/hop-dong', label: 'Hợp đồng' },
    { path: '/dong-ho', label: 'Đồng hồ' },
    { path: '/hoa-don', label: 'Hóa đơn' },
    { path: '/email', label: 'Email' },
  ];

  return (
    <div className="layout-root">
      <nav className="top-nav">
        <div className="top-nav-brand" onClick={() => navigate('/')}>
          <span className="brand-title">Minh An</span>
          <span className="brand-sub">Quản lý trọ</span>
        </div>
        
        <div className="top-nav-links">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) => `top-nav-item ${isActive ? 'active' : ''}`}
            >
              {item.label}
            </NavLink>
          ))}
        </div>

        <div className="top-nav-user">
          <span className="user-name">{user?.full_name}</span>
          <button className="btn-vat logout-btn" onClick={() => { logout(); navigate('/dang-nhap'); }}>
            Đăng xuất
          </button>
        </div>
      </nav>
      
      <main className="layout-main">
        <Outlet />
      </main>
    </div>
  );
}