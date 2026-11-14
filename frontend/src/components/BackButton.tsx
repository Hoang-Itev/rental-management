import { useNavigate } from 'react-router-dom';

export function BackButton({ to, label = 'Quay lại' }: { to?: string; label?: string }) {
  const navigate = useNavigate();
  return (
    <button
      className="btn-secondary"
      onClick={() => (to ? navigate(to) : navigate(-1))}
    >
      ← {label}
    </button>
  );
}