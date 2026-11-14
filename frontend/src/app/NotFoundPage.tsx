import { useNavigate } from 'react-router-dom';

export function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <div className="page-container">
      <h1 className="page-title">Không tìm thấy trang</h1>
      <p className="text-muted">Đường dẫn không tồn tại hoặc bạn không có quyền truy cập.</p>
      <button className="btn-primary" style={{ marginTop: 20 }} onClick={() => navigate('/')}>
        Về trang chủ
      </button>
    </div>
  );
}