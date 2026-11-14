import React from 'react';
import '../styles/scene.css';

export function AmbientEffects() {
  return (
    <>
      {/* Đom đóm (Hiện ở chế độ Tối) */}
      <div className="fireflies-scene">
        {Array.from({ length: 20 }).map((_, i) => (
          <span key={i} className="firefly"></span>
        ))}
      </div>

      {/* Lá liễu rơi (Hiện ở chế độ Sáng) */}
      <div className="leaves-fall">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} className="leaf-fall">
            <svg viewBox="0 0 10 20">
              <ellipse cx="5" cy="10" rx="3" ry="9" fill="var(--moss)" opacity=".85" />
              <line x1="5" y1="1" x2="5" y2="19" stroke="var(--moss-2)" strokeWidth=".5" />
            </svg>
          </div>
        ))}
      </div>
    </>
  );
}