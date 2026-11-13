import type { RoomOut } from '../../lib/api/types';

export function RoomSvg({ room }: { room: RoomOut }) {
  const state = room.display_occupancy;
  const signGradientId = `sign-${room.id}`;
  const signFrom = state === 'OCCUPIED' ? '#e8472b' : state === 'VACANT' ? '#6bbfab' : '#7a7a7a';
  const signTo = state === 'OCCUPIED' ? '#8a1e10' : state === 'VACANT' ? '#2a5f52' : '#3a3a3a';
  const wallColor = state === 'INACTIVE' ? '#8a7a5a' : state === 'VACANT' ? '#c9b088' : '#d9c398';
  const wallShadow = state === 'INACTIVE' ? '#5a4a3a' : '#a89070';

  return (
    <svg viewBox="0 0 240 320" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id={signGradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={signFrom} />
          <stop offset="100%" stopColor={signTo} />
        </linearGradient>
        <linearGradient id={`wall-${room.id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={wallColor} />
          <stop offset="100%" stopColor={wallShadow} />
        </linearGradient>
      </defs>

      <ellipse cx="120" cy="315" rx="100" ry="6" fill="#000" opacity=".3" />

      {/* Mái */}
      <g className="roof">
        <path
          d="M15 30 L120 5 L225 30 L215 40 L25 40 Z"
          fill="var(--tile)"
          stroke="var(--tile-2)"
          strokeWidth="2"
        />
        <path d="M15 30 Q10 20 5 25 Q12 28 15 30" fill="var(--tile-2)" stroke="var(--tile-hi)" strokeWidth="1" />
        <path d="M225 30 Q230 20 235 25 Q228 28 225 30" fill="var(--tile-2)" stroke="var(--tile-hi)" strokeWidth="1" />
      </g>

      <rect x="20" y="40" width="200" height="14" fill="var(--wood-3)" stroke="var(--wood-2)" strokeWidth="1" />

      {/* Cửa sổ */}
      <rect x="70" y="58" width="100" height="50" fill="var(--night-2)" stroke="var(--wood-2)" strokeWidth="3" />

      {/* Biển hiệu */}
      <rect x="90" y="125" width="60" height="22" fill={`url(#${signGradientId})`} stroke="var(--gold-3)" strokeWidth="1" />
      <text
        x="120"
        y="140"
        textAnchor="middle"
        fontFamily="'Noto Serif Display', serif"
        fontSize="11"
        fontWeight="600"
        fill="var(--gold-2)"
        letterSpacing="2"
      >
        {room.room_code}
      </text>

      {/* Cửa */}
      <g className="doors">
        <rect x="65" y="160" width="110" height="130" fill="var(--night-1)" opacity=".9" />
        <g className="door-left">
          <rect x="65" y="160" width="55" height="130" fill="var(--wood-3)" stroke="var(--wood-2)" strokeWidth="2" />
          <circle cx="115" cy="225" r="3" fill="var(--gold)" stroke="var(--gold-3)" strokeWidth="1" />
        </g>
        <g className="door-right">
          <rect x="120" y="160" width="55" height="130" fill="var(--wood-3)" stroke="var(--wood-2)" strokeWidth="2" />
          <circle cx="125" cy="225" r="3" fill="var(--gold)" stroke="var(--gold-3)" strokeWidth="1" />
        </g>
      </g>

      {/* Đèn lồng */}
      <g className="lantern-group">
        <circle cx="200" cy="85" r="20" fill="var(--cinnabar)" opacity=".25" className="lantern-halo" />
        <line x1="200" y1="55" x2="200" y2="70" stroke="var(--ink-dim)" strokeWidth="1" />
        <ellipse cx="200" cy="82" rx="12" ry="15" fill="var(--cinnabar)" stroke="var(--cinnabar-2)" strokeWidth="1" />
        <rect x="196" y="95" width="8" height="6" fill="var(--gold)" rx="1" />
      </g>
    </svg>
  );
}