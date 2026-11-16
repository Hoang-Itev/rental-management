import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { ApiError } from '../../lib/api/client';
import { PasswordInput } from '../../components/PasswordInput';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate('/', { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError('Email hoặc mật khẩu không đúng.');
      } else {
        setError('Không đăng nhập được. Vui lòng kiểm tra kết nối tới máy chủ.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-shell" style={{ background: 'radial-gradient(ellipse at 50% 0%, #1c2436, #0a0e17 60%, #000)' }}>
      {/* Hiệu ứng đèn lồng bay lơ lửng */}
      <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none' }}>
        <div style={{ position: 'absolute', top: 20, left: 30, fontSize: 40, animation: 'lanternSwing 3s infinite alternate' }}>🏮</div>
        <div style={{ position: 'absolute', top: 100, right: 50, fontSize: 40, animation: 'lanternSwing 4s infinite alternate-reverse' }}>🏮</div>
      </div>

      <form className="login-card" onSubmit={onSubmit} style={{ position: 'relative', zIndex: 10, border: '2px solid #8a6a1e', background: 'rgba(28, 36, 54, 0.95)', boxShadow: '0 0 50px rgba(212, 163, 64, 0.3)' }}>
                <div className="login-eyebrow" style={{ color: 'var(--gold-2)', opacity: 0.9 }}>Nhà trọ Minh An · Hội An</div>
        <h1 className="login-title">Phố cổ</h1>
                <div className="login-subtitle" style={{ color: 'var(--gold-2)', opacity: 0.9, marginBottom: 24 }}>Đăng nhập để quản lý khu trọ</div>

        <div className="login-field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <PasswordInput 
          id="password"
          label="Mật khẩu"
          value={password}
          onChange={setPassword}
          required
        />

        {error && <div className="login-error">{error}</div>}

        <button className="login-submit" type="submit" disabled={submitting}>
          {submitting ? 'Đang đăng nhập…' : 'Đăng nhập'}
        </button>
      </form>
    </div>
  );
}