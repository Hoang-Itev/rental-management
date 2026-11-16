import { useState } from 'react';
import { api, ApiError } from '../../lib/api/client';
import { PasswordInput } from '../../components/PasswordInput';

export default function ChangePasswordPage() {
  const [oldPass, setOldPass] = useState('');
  const [newPass, setNewPass] = useState('');
  const [confirmPass, setConfirmPass] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (newPass.length < 12) {
      setError('Mật khẩu mới phải có ít nhất 12 ký tự.');
      return;
    }
    if (!/[A-Z]/.test(newPass)) {
      setError('Mật khẩu phải có ít nhất 1 chữ in hoa.');
      return;
    }
    if (!/[a-z]/.test(newPass)) {
      setError('Mật khẩu phải có ít nhất 1 chữ thường.');
      return;
    }
    if (!/[0-9]/.test(newPass)) {
      setError('Mật khẩu phải có ít nhất 1 chữ số.');
      return;
    }
    if (!/[!@#$%^&*(),.?":{}|<>]/.test(newPass)) {
      setError('Mật khẩu phải có ít nhất 1 ký tự đặc biệt.');
      return;
    }
    if (newPass !== confirmPass) {
      setError('Mật khẩu xác nhận không khớp.');
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/api/v1/auth/change-password', {
        old_password: oldPass,
        new_password: newPass,
      });
      setSuccess('Đổi mật khẩu thành công!');
      setOldPass(''); setNewPass(''); setConfirmPass('');
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message || 'Đổi mật khẩu thất bại.');
      } else {
        setError('Lỗi kết nối.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-container" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '80vh', position: 'relative', overflow: 'hidden' }}>
      
      {/* HIỆU ỨNG MÂY VÀ ĐÈN LỒNG */}
      <style>{`
        @keyframes floatCloud {
          0% { transform: translateX(-20px); }
          50% { transform: translateX(30px); }
          100% { transform: translateX(-20px); }
        }
        @keyframes swingLantern {
          0% { transform: rotate(-15deg); }
          100% { transform: rotate(15deg); }
        }
        .decor-cloud { opacity: 0.6; filter: drop-shadow(0 0 10px rgba(0,0,0,0.1)); }
        body.dawn .decor-cloud { opacity: 0.8; filter: drop-shadow(0 0 10px rgba(0,0,0,0.3)); }
      `}</style>
      
      {/* Mây bay phía sau (Đổi màu đậm hơn để thấy trên nền sáng) */}
      <div className="decor-cloud" style={{ position: 'absolute', top: '15%', left: '10%', fontSize: 90, animation: 'floatCloud 15s infinite ease-in-out', color: '#8a7a5a' }}>☁️</div>
      <div className="decor-cloud" style={{ position: 'absolute', top: '25%', right: '10%', fontSize: 110, animation: 'floatCloud 20s infinite ease-in-out reverse', color: '#8a7a5a' }}>☁️</div>
      <div className="decor-cloud" style={{ position: 'absolute', bottom: '15%', left: '15%', fontSize: 70, animation: 'floatCloud 18s infinite ease-in-out', color: '#8a7a5a' }}>☁️</div>
      <div className="decor-cloud" style={{ position: 'absolute', bottom: '20%', right: '20%', fontSize: 80, animation: 'floatCloud 22s infinite ease-in-out reverse', color: '#8a7a5a' }}>☁️</div>

      {/* Đèn lồng treo rải rác xung quanh */}
      <div style={{ position: 'absolute', top: '-20px', left: 'calc(50% - 300px)', fontSize: 60, animation: 'swingLantern 3s infinite alternate', transformOrigin: 'top center', zIndex: 5 }}>🏮</div>
      <div style={{ position: 'absolute', top: '-40px', right: 'calc(50% - 300px)', fontSize: 60, animation: 'swingLantern 3.5s infinite alternate-reverse', transformOrigin: 'top center', zIndex: 5 }}>🏮</div>
      <div style={{ position: 'absolute', top: '20%', left: '5%', fontSize: 40, animation: 'swingLantern 4s infinite alternate', transformOrigin: 'top center', opacity: 0.8 }}>🏮</div>
      <div style={{ position: 'absolute', top: '30%', right: '5%', fontSize: 50, animation: 'swingLantern 2.5s infinite alternate-reverse', transformOrigin: 'top center', opacity: 0.8 }}>🏮</div>
      <div style={{ position: 'absolute', bottom: '10%', left: '25%', fontSize: 30, animation: 'swingLantern 5s infinite alternate', transformOrigin: 'top center', opacity: 0.6 }}>🏮</div>

      <form className="login-card" onSubmit={handleSubmit} style={{ position: 'relative', zIndex: 10, width: '100%', maxWidth: 460, border: '2px solid var(--gold-3)', background: 'var(--night-2)', boxShadow: '0 10px 40px rgba(0,0,0,0.5)' }}>
        
        {/* Mái ngói nhà cổ phía trên form */}
                {/* Mái ngói nhà cổ phía trên form - ĐỎ GẠCH */}
        <div style={{ 
          position: 'absolute', 
          top: -16, 
          left: -10, 
          right: -10, 
          height: 18, 
          background: 'repeating-linear-gradient(90deg, var(--cinnabar-2), var(--cinnabar-2) 12px, var(--cinnabar-3) 12px, var(--cinnabar-3) 24px)', 
          borderRadius: '8px 8px 0 0', 
          borderBottom: '3px solid var(--gold-2)', 
          boxShadow: '0 6px 12px rgba(0,0,0,0.5)' 
        }}></div>

        <div className="login-eyebrow" style={{ textAlign: 'center', marginTop: 10 }}>Bảo mật tài khoản</div>
        <h1 className="login-title" style={{ textAlign: 'center', fontSize: 32, marginBottom: 20 }}>Đổi Mật Khẩu</h1>

        <PasswordInput id="old" label="Mật khẩu hiện tại" value={oldPass} onChange={setOldPass} required />
        
        <div style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: -10, marginBottom: 16, fontStyle: 'italic' }}>
          (Yêu cầu: ≥ 12 ký tự, gồm chữ hoa, chữ thường, số và ký tự đặc biệt)
        </div>
        
        <PasswordInput id="new" label="Mật khẩu mới" value={newPass} onChange={setNewPass} required />
        <PasswordInput id="confirm" label="Xác nhận mật khẩu mới" value={confirmPass} onChange={setConfirmPass} required />

        {error && <div className="login-error">{error}</div>}
        {success && <div className="login-error" style={{ color: 'var(--jade)', borderColor: 'var(--jade)', backgroundColor: 'rgba(61, 138, 122, 0.1)' }}>{success}</div>}

        <button className="login-submit" type="submit" disabled={submitting} style={{ marginTop: 10 }}>
          {submitting ? 'Đang xử lý…' : 'Xác nhận đổi mật khẩu'}
        </button>
      </form>
    </div>
  );
}