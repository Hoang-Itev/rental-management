import { useState } from 'react';

interface Props {
  id: string;
  value: string;
  onChange: (val: string) => void;
  label: string;
  placeholder?: string;
  required?: boolean;
}

export function PasswordInput({ id, value, onChange, label, placeholder, required }: Props) {
  const [show, setShow] = useState(false);

  return (
    <div className="login-field" style={{ position: 'relative' }}>
      <label htmlFor={id}>{label}</label>
      <div style={{ position: 'relative' }}>
        <input
          id={id}
          type={show ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          required={required}
          style={{ paddingRight: '40px' }} // Chừa chỗ cho con mắt
        />
        <button
          type="button"
          onClick={() => setShow(!show)}
          style={{
            position: 'absolute',
            right: '10px',
            top: '50%',
            transform: 'translateY(-50%)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--ink-soft)',
            fontSize: '18px',
          }}
        >
          {show ? '👁️' : '👁️‍🗨️'}
        </button>
      </div>
    </div>
  );
}