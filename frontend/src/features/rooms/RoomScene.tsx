import { useEffect, useRef } from 'react';
import type { RoomOut } from '../../lib/api/types';
import '../../styles/scene.css';

interface Props {
  rooms: RoomOut[];
  onSelect: (room: RoomOut) => void;
  mode: 'dawn' | 'night';
}

const RoomItem = ({ r, onClick }: { r: RoomOut, onClick: () => void }) => {
  const state = r.display_occupancy;
  const isOccupied = state === 'OCCUPIED';
  const isVacant = state === 'VACANT';
  const catColor = isOccupied ? 'var(--plum)' : 'var(--stone)';
  const hasCat = isOccupied || isVacant;
  const hasDragon = isOccupied;

  // Tạo ID duy nhất cho gradient của từng phòng để tránh trùng lặp
  const uid = r.id.replace(/[^a-zA-Z0-9]/g, '');

  return (
    <div className={`shop ${isOccupied ? 'occupied' : isVacant ? 'vacant' : 'inactive'}`} onClick={onClick}>
      <svg viewBox="0 0 240 320" preserveAspectRatio="xMidYMid meet">
        {/* NHÚNG DEFS VÀO TỪNG PHÒNG (giống file HTML mẫu) */}
        <defs>
          <linearGradient id={`tile-grad-${uid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--tile-hi)" />
            <stop offset="100%" stopColor="var(--tile-2)" />
          </linearGradient>
          <linearGradient id={`wood-grad-${uid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--wood-3)" />
            <stop offset="100%" stopColor="var(--wood-2)" />
          </linearGradient>
          <linearGradient id={`sign-red-${uid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#e8472b" />
            <stop offset="100%" stopColor="#8a1e10" />
          </linearGradient>
          <linearGradient id={`sign-jade-${uid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6bbfab" />
            <stop offset="100%" stopColor="#2a5f52" />
          </linearGradient>
          <linearGradient id={`sign-stone-${uid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#7a7a7a" />
            <stop offset="100%" stopColor="#3a3a3a" />
          </linearGradient>
          <linearGradient id={`lantern-grad-${uid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--cinnabar-3)" />
            <stop offset="50%" stopColor="var(--cinnabar)" />
            <stop offset="100%" stopColor="var(--cinnabar-2)" />
          </linearGradient>
          <radialGradient id={`lantern-halo-grad-${uid}`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--cinnabar-3)" stopOpacity=".9" />
            <stop offset="60%" stopColor="var(--cinnabar)" stopOpacity=".3" />
            <stop offset="100%" stopColor="var(--cinnabar)" stopOpacity="0" />
          </radialGradient>
        </defs>

        <ellipse cx="120" cy="315" rx="100" ry="6" fill="#000" opacity=".3" />

        <g className="roof">
          <path d="M15 30 L120 5 L225 30 L215 40 L25 40 Z" fill={`url(#tile-grad-${uid})`} stroke="var(--tile-2)" strokeWidth="2" />
          <path d="M30 30 L45 30 L43 36 L28 36 Z" fill="var(--tile-hi)" opacity=".5" />
          <path d="M50 30 L65 30 L63 36 L48 36 Z" fill="var(--tile-hi)" opacity=".5" />
          <path d="M70 30 L85 30 L83 36 L68 36 Z" fill="var(--tile-hi)" opacity=".5" />
          <path d="M90 30 L105 30 L103 36 L88 36 Z" fill="var(--tile-hi)" opacity=".5" />
          <path d="M110 30 L125 30 L123 36 L108 36 Z" fill="var(--tile-hi)" opacity=".5" />
          <path d="M130 30 L145 30 L143 36 L128 36 Z" fill="var(--tile-hi)" opacity=".5" />
          <path d="M150 30 L165 30 L163 36 L148 36 Z" fill="var(--tile-hi)" opacity=".5" />
          <path d="M170 30 L185 30 L183 36 L168 36 Z" fill="var(--tile-hi)" opacity=".5" />
          <path d="M190 30 L205 30 L203 36 L188 36 Z" fill="var(--tile-hi)" opacity=".5" />
          <path d="M15 30 Q10 20 5 25 Q12 28 15 30" fill="var(--tile-2)" stroke="var(--tile-hi)" strokeWidth="1" />
          <path d="M225 30 Q230 20 235 25 Q228 28 225 30" fill="var(--tile-2)" stroke="var(--tile-hi)" strokeWidth="1" />
          {hasDragon && (
            <g>
              <path d="M40 25 Q55 15 70 22 Q85 28 100 20 Q115 12 130 22 Q145 28 160 20 Q175 14 190 22" stroke="var(--gold)" strokeWidth="2" fill="none" opacity=".8" />
              <circle cx="70" cy="22" r="1.5" fill="var(--cinnabar-3)" />
              <circle cx="130" cy="22" r="1.5" fill="var(--cinnabar-3)" />
              <circle cx="190" cy="22" r="1.5" fill="var(--cinnabar-3)" />
            </g>
          )}
        </g>

        <rect x="20" y="40" width="200" height="14" fill={`url(#wood-grad-${uid})`} stroke="var(--wood-2)" strokeWidth="1" />
        <line x1="25" y1="47" x2="215" y2="47" stroke="var(--gold-3)" strokeWidth="1" strokeDasharray="2 3" />
        <circle cx="28" cy="47" r="4" fill="var(--gold)" opacity=".7" />
        <circle cx="212" cy="47" r="4" fill="var(--gold)" opacity=".7" />

        <rect x="70" y="58" width="100" height="50" fill="var(--night-2)" stroke="var(--wood-2)" strokeWidth="3" />
        <rect x="73" y="61" width="94" height="44" fill={`url(#wood-grad-${uid})`} opacity=".3" />
        <line x1="73" y1="66" x2="167" y2="66" stroke="var(--wood-2)" strokeWidth="1" opacity=".8" />
        <line x1="73" y1="72" x2="167" y2="72" stroke="var(--wood-2)" strokeWidth="1" opacity=".8" />
        <line x1="73" y1="78" x2="167" y2="78" stroke="var(--wood-2)" strokeWidth="1" opacity=".8" />
        <line x1="73" y1="84" x2="167" y2="84" stroke="var(--wood-2)" strokeWidth="1" opacity=".8" />
        <line x1="73" y1="90" x2="167" y2="90" stroke="var(--wood-2)" strokeWidth="1" opacity=".8" />
        <line x1="73" y1="96" x2="167" y2="96" stroke="var(--wood-2)" strokeWidth="1" opacity=".8" />
        <line x1="100" y1="58" x2="100" y2="108" stroke="var(--wood-2)" strokeWidth="1" opacity=".8" />
        <line x1="140" y1="58" x2="140" y2="108" stroke="var(--wood-2)" strokeWidth="1" opacity=".8" />
        <circle cx="120" cy="83" r="10" fill="none" stroke="var(--gold-3)" strokeWidth="1" opacity=".7" />
        <path d="M115 78 L125 78 M115 88 L125 88 M120 75 L120 91" stroke="var(--gold-3)" strokeWidth="1" opacity=".5" />

        <rect x="65" y="110" width="110" height="6" fill="var(--wood-3)" stroke="var(--wood-2)" strokeWidth="1" />
        <g className="flower-group">
          <circle cx="80" cy="105" r="3" fill="var(--cinnabar)" />
          <circle cx="95" cy="103" r="3" fill="var(--amber)" />
          <circle cx="110" cy="105" r="3" fill="var(--gold-2)" />
          <circle cx="125" cy="103" r="3" fill="var(--cinnabar-3)" />
          <circle cx="140" cy="105" r="3" fill="var(--jade-hi)" />
          <circle cx="155" cy="103" r="3" fill="var(--plum)" />
          <ellipse cx="80" cy="110" rx="4" ry="2" fill="var(--moss)" />
          <ellipse cx="110" cy="110" rx="4" ry="2" fill="var(--moss-2)" />
          <ellipse cx="140" cy="110" rx="4" ry="2" fill="var(--moss)" />
        </g>

        <g className="sign-group">
          <rect x="90" y="125" width="60" height="22" fill={isOccupied ? `url(#sign-red-${uid})` : isVacant ? `url(#sign-jade-${uid})` : `url(#sign-stone-${uid})`} stroke="var(--gold-3)" strokeWidth="1" />
          <rect x="93" y="128" width="54" height="16" fill="none" stroke="var(--gold-2)" strokeWidth=".5" opacity=".5" />
          <text x="120" y="140" textAnchor="middle" fontFamily="'Noto Serif Display', serif" fontSize="11" fontWeight="600" fill="var(--gold-2)" letterSpacing="2">{r.room_code}</text>
        </g>

        <g className="doors">
          <rect x="65" y="160" width="110" height="130" fill="var(--night-1)" opacity=".9" />
          <rect x="80" y="250" width="30" height="3" fill="var(--wood-3)" />
          <rect x="82" y="253" width="3" height="15" fill="var(--wood-3)" />
          <rect x="105" y="253" width="3" height="15" fill="var(--wood-3)" />
          <ellipse cx="120" cy="230" rx="60" ry="40" fill="var(--amber)" opacity=".15" />
          
          <g className="door-left">
            <rect x="65" y="160" width="55" height="130" fill={`url(#wood-grad-${uid})`} stroke="var(--wood-2)" strokeWidth="2" />
            <line x1="92" y1="160" x2="92" y2="290" stroke="var(--wood-2)" strokeWidth="1" />
            <circle cx="75" cy="175" r="2" fill="var(--gold-3)" /><circle cx="110" cy="175" r="2" fill="var(--gold-3)" />
            <circle cx="75" cy="200" r="2" fill="var(--gold-3)" /><circle cx="110" cy="200" r="2" fill="var(--gold-3)" />
            <circle cx="75" cy="225" r="2" fill="var(--gold-3)" /><circle cx="110" cy="225" r="2" fill="var(--gold-3)" />
            <circle cx="75" cy="250" r="2" fill="var(--gold-3)" /><circle cx="110" cy="250" r="2" fill="var(--gold-3)" />
            <circle cx="115" cy="225" r="3" fill="var(--gold)" stroke="var(--gold-3)" strokeWidth="1" />
          </g>
          <g className="door-right">
            <rect x="120" y="160" width="55" height="130" fill={`url(#wood-grad-${uid})`} stroke="var(--wood-2)" strokeWidth="2" />
            <line x1="147" y1="160" x2="147" y2="290" stroke="var(--wood-2)" strokeWidth="1" />
            <circle cx="130" cy="175" r="2" fill="var(--gold-3)" /><circle cx="165" cy="175" r="2" fill="var(--gold-3)" />
            <circle cx="130" cy="200" r="2" fill="var(--gold-3)" /><circle cx="165" cy="200" r="2" fill="var(--gold-3)" />
            <circle cx="130" cy="225" r="2" fill="var(--gold-3)" /><circle cx="165" cy="225" r="2" fill="var(--gold-3)" />
            <circle cx="130" cy="250" r="2" fill="var(--gold-3)" /><circle cx="165" cy="250" r="2" fill="var(--gold-3)" />
            <circle cx="125" cy="225" r="3" fill="var(--gold)" stroke="var(--gold-3)" strokeWidth="1" />
          </g>
        </g>

        {hasCat && (
          <g className="cat-silhouette" transform={`translate(${isOccupied ? 170 : 60}, 18)`}>
            <ellipse cx="0" cy="0" rx="10" ry="6" fill={catColor} />
            <circle cx="6" cy="-4" r="5" fill={catColor} />
            <path className="cat-ear" d="M2 -8 L4 -12 L7 -9 Z" fill={catColor} />
            <path className="cat-ear" d="M9 -8 L11 -12 L13 -9 Z" fill={catColor} />
            <circle cx="8" cy="-5" r=".8" fill="var(--gold-2)" />
            <circle cx="10" cy="-5" r=".8" fill="var(--gold-2)" />
            <path className="cat-tail" d="M-9 0 Q-16 -4 -18 -12" stroke={catColor} strokeWidth="2" fill="none" strokeLinecap="round" />
          </g>
        )}

        <ellipse className="room-glow" cx="120" cy="200" rx="110" ry="140" fill={`url(#lantern-halo-grad-${uid})`} opacity="0" />

        <g className="lantern-group">
          <circle cx="200" cy="85" r="30" fill={`url(#lantern-halo-grad-${uid})`} className="lantern-halo" />
          <line x1="200" y1="55" x2="200" y2="70" stroke="var(--ink-dim)" strokeWidth="1" />
          <ellipse cx="200" cy="82" rx="12" ry="15" fill={`url(#lantern-grad-${uid})`} stroke="var(--cinnabar-2)" strokeWidth="1" />
          <line x1="200" y1="70" x2="200" y2="94" stroke="var(--gold-3)" strokeWidth=".5" opacity=".6" />
          <rect x="196" y="95" width="8" height="6" fill="var(--gold)" rx="1" />
        </g>

        <g className="windchime-group">
          <line x1="50" y1="55" x2="50" y2="100" stroke="var(--ink-dim)" strokeWidth=".8" />
          <rect x="46" y="100" width="8" height="6" fill="var(--gold)" rx="1" />
          <rect x="46" y="108" width="8" height="6" fill="var(--gold)" rx="1" />
          <rect x="46" y="116" width="8" height="6" fill="var(--gold)" rx="1" />
        </g>

        <circle className="dust-dot" cx="80" cy="280" r="2" fill="var(--gold-2)" />
        <circle className="dust-dot" cx="100" cy="270" r="2" fill="var(--gold-2)" />
        <circle className="dust-dot" cx="140" cy="275" r="2" fill="var(--gold-2)" />
        <circle className="dust-dot" cx="160" cy="285" r="2" fill="var(--gold-2)" />
        <circle className="dust-dot" cx="120" cy="290" r="2" fill="var(--gold-2)" />

        <path className="incense-smoke" d="M120 290 Q118 280 120 270 Q122 260 120 250" stroke="var(--ink-soft)" strokeWidth="1" fill="none" opacity=".6" />
      </svg>
    </div>
  );
};

export function RoomScene({ rooms, onSelect, mode }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.body.classList.toggle('dawn', mode === 'dawn');
  }, [mode]);

  const stars = Array.from({ length: 80 }).map((_, i) => (
    <span
      key={i}
      className={`star ${Math.random() > 0.7 ? 'big' : ''}`}
      style={{
        left: `${Math.random() * 100}%`,
        top: `${Math.random() * 100}%`,
        animationDelay: `${Math.random() * 4}s`,
        animationDuration: `${3 + Math.random() * 4}s`,
      }}
    />
  ));

  return (
    <div className="scene-root">
      <div className="stars" id="stars">{stars}</div>
      <div className={`celestial ${mode === 'dawn' ? 'sun' : 'moon'}`} id="celestial"></div>

      <div className="clouds">
        <div className="cloud c1"></div><div className="cloud c2"></div>
        <div className="cloud c3"></div><div className="cloud c4"></div>
      </div>

      <div className="mountains">
        <div className="mountain m1"></div>
        <div className="mountain m2"></div>
        <div className="mountain m3"></div>
      </div>

      <div 
        className="giant-willow" 
        style={{ 
          left: '50%', 
          transform: 'translateX(-50%)', 
          bottom: '200px', 
          width: '100%', 
          maxWidth: '800px', 
          height: 'auto', 
          maxHeight: '1200px',
          position: 'absolute',
          overflow: 'hidden'
        }}
      >
        <svg viewBox="0 0 520 900" preserveAspectRatio="xMidYMax meet">
          <path d="M260 900 Q240 700 250 500 Q260 350 230 200 Q220 150 240 100" stroke="var(--wood-3)" strokeWidth="22" fill="none" strokeLinecap="round" opacity=".95"/>
          <path d="M260 900 Q240 700 250 500 Q260 350 230 200 Q220 150 240 100" stroke="var(--wood-hi)" strokeWidth="4" fill="none" strokeLinecap="round" opacity=".4"/>
          <path d="M255 850 Q245 750 252 650" stroke="var(--wood-2)" strokeWidth="2" fill="none" opacity=".6"/>
          <path d="M265 780 Q258 700 262 620" stroke="var(--wood-2)" strokeWidth="2" fill="none" opacity=".6"/>
          <path d="M250 500 Q180 420 120 350" stroke="var(--wood-3)" strokeWidth="10" fill="none" strokeLinecap="round"/>
          <path d="M250 500 Q320 420 380 340" stroke="var(--wood-3)" strokeWidth="10" fill="none" strokeLinecap="round"/>
          <path d="M240 320 Q180 260 130 210" stroke="var(--wood-3)" strokeWidth="8" fill="none" strokeLinecap="round"/>
          <path d="M240 320 Q300 260 360 220" stroke="var(--wood-3)" strokeWidth="8" fill="none" strokeLinecap="round"/>
          <path d="M235 180 Q200 130 160 100" stroke="var(--wood-3)" strokeWidth="7" fill="none" strokeLinecap="round"/>
          <path d="M235 180 Q280 130 320 100" stroke="var(--wood-3)" strokeWidth="7" fill="none" strokeLinecap="round"/>
          <g className="gw-branch" style={{transformOrigin:'120px 350px'}}>
            <path d="M120 350 Q100 500 90 700 Q85 800 80 880" stroke="var(--moss)" strokeWidth="3" fill="none" opacity=".9"/>
            <ellipse cx="80" cy="880" rx="4" ry="14" fill="var(--moss)"/>
            <ellipse cx="90" cy="800" rx="3" ry="10" fill="var(--moss-3)"/>
          </g>
          <g className="gw-branch" style={{transformOrigin:'140px 340px'}}>
            <path d="M140 340 Q130 500 125 680 Q120 790 118 860" stroke="var(--moss)" strokeWidth="3" fill="none" opacity=".9"/>
            <ellipse cx="118" cy="860" rx="4" ry="14" fill="var(--moss-2)"/>
          </g>
          <g className="gw-branch" style={{transformOrigin:'180px 320px'}}>
            <path d="M180 320 Q170 480 165 650 Q162 780 160 870" stroke="var(--moss)" strokeWidth="3" fill="none" opacity=".85"/>
            <ellipse cx="160" cy="870" rx="4" ry="14" fill="var(--moss)"/>
          </g>
          <g className="gw-branch" style={{transformOrigin:'130px 210px'}}>
            <path d="M130 210 Q110 380 100 560 Q95 700 92 820" stroke="var(--moss)" strokeWidth="3" fill="none" opacity=".85"/>
            <ellipse cx="92" cy="820" rx="4" ry="14" fill="var(--moss-3)"/>
          </g>
          <g className="gw-branch" style={{transformOrigin:'380px 340px'}}>
            <path d="M380 340 Q400 500 408 700 Q412 800 415 880" stroke="var(--moss)" strokeWidth="3" fill="none" opacity=".9"/>
            <ellipse cx="415" cy="880" rx="4" ry="14" fill="var(--moss)"/>
          </g>
          <g className="gw-branch" style={{transformOrigin:'360px 360px'}}>
            <path d="M360 360 Q375 510 380 690 Q383 790 385 860" stroke="var(--moss)" strokeWidth="3" fill="none" opacity=".85"/>
            <ellipse cx="385" cy="860" rx="4" ry="14" fill="var(--moss-2)"/>
          </g>
          <g className="gw-branch" style={{transformOrigin:'320px 300px'}}>
            <path d="M320 300 Q340 470 345 650 Q348 780 350 870" stroke="var(--moss)" strokeWidth="3" fill="none" opacity=".85"/>
            <ellipse cx="350" cy="870" rx="4" ry="14" fill="var(--moss)"/>
          </g>
          <g className="gw-branch" style={{transformOrigin:'360px 220px'}}>
            <path d="M360 220 Q380 380 390 560 Q395 700 398 820" stroke="var(--moss)" strokeWidth="3" fill="none" opacity=".8"/>
            <ellipse cx="398" cy="820" rx="4" ry="14" fill="var(--moss-3)"/>
          </g>
          <g className="gw-branch" style={{transformOrigin:'200px 280px'}}>
            <path d="M200 280 Q195 450 192 650 Q190 780 188 870" stroke="var(--moss)" strokeWidth="3" fill="none" opacity=".9"/>
            <ellipse cx="188" cy="870" rx="4" ry="14" fill="var(--moss)"/>
          </g>
          <g className="gw-branch" style={{transformOrigin:'300px 280px'}}>
            <path d="M300 280 Q305 450 308 650 Q310 780 312 870" stroke="var(--moss)" strokeWidth="3" fill="none" opacity=".9"/>
            <ellipse cx="312" cy="870" rx="4" ry="14" fill="var(--moss-2)"/>
          </g>
          <g className="gw-branch" style={{transformOrigin:'230px 170px'}}>
            <path d="M230 170 Q225 380 222 580 Q220 720 218 850" stroke="var(--moss)" strokeWidth="3" fill="none" opacity=".85"/>
            <ellipse cx="218" cy="850" rx="4" ry="14" fill="var(--moss)"/>
          </g>
          <g className="gw-branch" style={{transformOrigin:'270px 170px'}}>
            <path d="M270 170 Q275 380 278 580 Q280 720 282 850" stroke="var(--moss)" strokeWidth="3" fill="none" opacity=".85"/>
            <ellipse cx="282" cy="850" rx="4" ry="14" fill="var(--moss-3)"/>
          </g>
        </svg>
      </div>

      <div className="birds">
        {[1,2,3,4,5,6].map(i => (
          <div key={i} className={`bird b${i}`}><svg viewBox="0 0 16 6"><path d="M1 4 Q4 1 8 4 Q12 1 15 4"/></svg></div>
        ))}
      </div>

      <div className="sky-lanterns">
        <div className="sky-lantern sl1"></div>
        <div className="sky-lantern sl2"></div>
        <div className="sky-lantern sl3"></div>
      </div>

      <div className="mist">
        <svg viewBox="0 0 1200 400" preserveAspectRatio="none">
          <path className="mist-path" d="M-100 200 Q200 150 400 200 T800 180 T1300 200 L1300 400 L-100 400 Z" fill="rgba(255,255,255,.15)" filter="blur(20px)"/>
        </svg>
      </div>

      <div className="butterflies">
        <div className="butterfly bf1"><svg viewBox="0 0 20 16"><ellipse className="wing-l" cx="6" cy="8" rx="5" ry="7" fill="var(--gold-2)" opacity=".85"/><ellipse className="wing-r" cx="14" cy="8" rx="5" ry="7" fill="var(--cinnabar-3)" opacity=".85"/><ellipse cx="10" cy="8" rx="1" ry="5" fill="var(--ink)"/></svg></div>
        <div className="butterfly bf2"><svg viewBox="0 0 20 16"><ellipse className="wing-l" cx="6" cy="8" rx="5" ry="7" fill="var(--jade-hi)" opacity=".85"/><ellipse className="wing-r" cx="14" cy="8" rx="5" ry="7" fill="var(--amber)" opacity=".85"/><ellipse cx="10" cy="8" rx="1" ry="5" fill="var(--ink)"/></svg></div>
        <div className="butterfly bf3"><svg viewBox="0 0 20 16"><ellipse className="wing-l" cx="6" cy="8" rx="5" ry="7" fill="var(--plum)" opacity=".85"/><ellipse className="wing-r" cx="14" cy="8" rx="5" ry="7" fill="var(--gold-2)" opacity=".85"/><ellipse cx="10" cy="8" rx="1" ry="5" fill="var(--ink)"/></svg></div>
      </div>

      

      

      <div className="facade" ref={containerRef}>
        {rooms.map((r) => (
          <RoomItem key={r.id} r={r} onClick={() => onSelect(r)} />
        ))}
      </div>

      <div className="river-scene">
        <div className="willow">
          <svg viewBox="0 0 200 300">
            <path d="M100 300 Q95 200 95 120 Q90 70 85 40" stroke="var(--wood-3)" strokeWidth="6" fill="none" strokeLinecap="round"/>
            <path d="M95 120 Q105 100 115 80" stroke="var(--wood-3)" strokeWidth="4" fill="none" strokeLinecap="round"/>
            <g className="branch" style={{transformOrigin:'95px 120px'}}><path d="M95 120 Q85 160 75 220 Q70 250 65 280" stroke="var(--moss)" strokeWidth="2" fill="none"/><ellipse cx="65" cy="280" rx="3" ry="8" fill="var(--moss)"/></g>
            <g className="branch" style={{transformOrigin:'95px 120px'}}><path d="M95 120 Q90 170 85 230" stroke="var(--moss)" strokeWidth="2" fill="none"/><ellipse cx="85" cy="230" rx="3" ry="8" fill="var(--moss-2)"/></g>
            <g className="branch" style={{transformOrigin:'100px 100px'}}><path d="M100 100 Q110 150 120 210 Q125 240 128 270" stroke="var(--moss)" strokeWidth="2" fill="none"/><ellipse cx="128" cy="270" rx="3" ry="8" fill="var(--moss)"/></g>
            <g className="branch" style={{transformOrigin:'105px 80px'}}><path d="M105 80 Q115 130 130 180 Q135 210 140 240" stroke="var(--moss)" strokeWidth="2" fill="none"/><ellipse cx="140" cy="240" rx="3" ry="8" fill="var(--moss-2)"/></g>
            <g className="branch" style={{transformOrigin:'85px 40px'}}><path d="M85 40 Q75 90 70 140 Q65 180 60 210" stroke="var(--moss)" strokeWidth="2" fill="none"/><ellipse cx="60" cy="210" rx="3" ry="8" fill="var(--moss)"/></g>
            <g className="branch" style={{transformOrigin:'90px 100px'}}><path d="M90 100 Q75 140 65 180 Q60 210 58 235" stroke="var(--moss)" strokeWidth="2" fill="none"/><ellipse cx="58" cy="235" rx="3" ry="8" fill="var(--moss-2)"/></g>
          </svg>
        </div>

        <div className="bamboo">
          <svg viewBox="0 0 140 280">
            <g className="stalk" style={{transformOrigin:'30px 280px'}}>
              <rect x="28" y="40" width="4" height="240" fill="var(--moss-2)"/>
              <rect x="28" y="80" width="4" height="2" fill="var(--moss)"/>
              <rect x="28" y="140" width="4" height="2" fill="var(--moss)"/>
              <rect x="28" y="200" width="4" height="2" fill="var(--moss)"/>
              <ellipse cx="30" cy="50" rx="8" ry="14" fill="var(--moss)"/>
              <ellipse cx="24" cy="100" rx="6" ry="10" fill="var(--moss-2)"/>
              <ellipse cx="36" cy="150" rx="7" ry="12" fill="var(--moss)"/>
            </g>
            <g className="stalk" style={{transformOrigin:'70px 280px'}}>
              <rect x="68" y="80" width="4" height="200" fill="var(--moss-2)"/>
              <rect x="68" y="120" width="4" height="2" fill="var(--moss)"/>
              <rect x="68" y="170" width="4" height="2" fill="var(--moss)"/>
              <ellipse cx="70" cy="90" rx="7" ry="12" fill="var(--moss)"/>
              <ellipse cx="62" cy="140" rx="6" ry="10" fill="var(--moss-2)"/>
            </g>
            <g className="stalk" style={{transformOrigin:'110px 280px'}}>
              <rect x="108" y="60" width="4" height="220" fill="var(--moss-2)"/>
              <rect x="108" y="100" width="4" height="2" fill="var(--moss)"/>
              <rect x="108" y="160" width="4" height="2" fill="var(--moss)"/>
              <ellipse cx="110" cy="70" rx="8" ry="14" fill="var(--moss)"/>
              <ellipse cx="102" cy="120" rx="6" ry="10" fill="var(--moss-2)"/>
              <ellipse cx="118" cy="180" rx="7" ry="12" fill="var(--moss)"/>
            </g>
          </svg>
        </div>

        <div className="stone-bridge">
          <svg viewBox="0 0 800 90" preserveAspectRatio="none">
            <path d="M0 90 L0 60 Q20 20 60 20 Q100 20 120 60 L180 60 Q200 20 240 20 Q280 20 300 60 L360 60 Q380 20 420 20 Q460 20 480 60 L540 60 Q560 20 600 20 Q640 20 660 60 L720 60 Q740 20 780 20 Q800 20 800 60 L800 90 Z" fill="var(--stone)" stroke="var(--stone-2)" strokeWidth="2"/>
            <path d="M60 90 Q60 50 120 50 Q180 50 180 90" fill="var(--night-1)" opacity=".8"/>
            <path d="M240 90 Q240 50 300 50 Q360 50 360 90" fill="var(--night-1)" opacity=".8"/>
            <path d="M420 90 Q420 50 480 50 Q540 50 540 90" fill="var(--night-1)" opacity=".8"/>
            <path d="M600 90 Q600 50 660 50 Q720 50 720 90" fill="var(--night-1)" opacity=".8"/>
            <line x1="0" y1="0" x2="800" y2="0" stroke="var(--stone-2)" strokeWidth="4"/>
            <line x1="20" y1="0" x2="20" y2="20" stroke="var(--stone-2)" strokeWidth="2"/>
            <line x1="100" y1="0" x2="100" y2="20" stroke="var(--stone-2)" strokeWidth="2"/>
            <line x1="200" y1="0" x2="200" y2="20" stroke="var(--stone-2)" strokeWidth="2"/>
            <line x1="300" y1="0" x2="300" y2="20" stroke="var(--stone-2)" strokeWidth="2"/>
            <line x1="400" y1="0" x2="400" y2="20" stroke="var(--stone-2)" strokeWidth="2"/>
            <line x1="500" y1="0" x2="500" y2="20" stroke="var(--stone-2)" strokeWidth="2"/>
            <line x1="600" y1="0" x2="600" y2="20" stroke="var(--stone-2)" strokeWidth="2"/>
            <line x1="700" y1="0" x2="700" y2="20" stroke="var(--stone-2)" strokeWidth="2"/>
            <line x1="780" y1="0" x2="780" y2="20" stroke="var(--stone-2)" strokeWidth="2"/>
            <path d="M20 40 Q40 30 60 40 Q80 35 100 42" stroke="var(--moss)" strokeWidth="2" fill="none" opacity=".6"/>
            <path d="M200 40 Q220 30 240 40 Q260 35 280 42" stroke="var(--moss)" strokeWidth="2" fill="none" opacity=".6"/>
            <path d="M500 40 Q520 30 540 40 Q560 35 580 42" stroke="var(--moss)" strokeWidth="2" fill="none" opacity=".6"/>
          </svg>
        </div>

        <div className="river">
          <div className="moon-reflect"></div>
        </div>

        <div className="koi koi-1">
          <svg viewBox="0 0 130 60">
            <g className="koi-body">
              <path d="M25 30 Q40 15 70 18 Q100 20 105 30 Q100 40 70 42 Q40 45 25 30 Z" fill="var(--koi-1)" stroke="var(--koi-3)" strokeWidth="1.5"/>
              <ellipse cx="55" cy="28" rx="14" ry="8" fill="var(--koi-2)" opacity=".9"/>
              <ellipse cx="85" cy="30" rx="8" ry="6" fill="var(--koi-2)" opacity=".85"/>
              <path d="M55 18 Q65 8 80 18" fill="var(--koi-2)" stroke="var(--koi-3)" strokeWidth="1" opacity=".85"/>
              <path d="M105 30 Q125 15 128 10 Q120 25 122 30 Q120 35 128 50 Q125 45 105 30 Z" fill="var(--koi-2)" stroke="var(--koi-3)" strokeWidth="1" opacity=".9"/>
              <path d="M45 22 Q40 12 35 15 Q42 22 45 22 Z" fill="var(--koi-2)" opacity=".8"/>
              <path d="M45 38 Q40 48 35 45 Q42 38 45 38 Z" fill="var(--koi-2)" opacity=".8"/>
              <path d="M60 38 Q58 46 55 46 Q60 40 60 38 Z" fill="var(--koi-2)" opacity=".7"/>
              <circle cx="35" cy="27" r="2" fill="var(--ink)"/>
              <circle cx="35" cy="33" r="2" fill="var(--ink)"/>
              <path d="M28 26 Q20 22 18 18" stroke="var(--koi-3)" strokeWidth="1" fill="none"/>
              <path d="M28 34 Q20 38 18 42" stroke="var(--koi-3)" strokeWidth="1" fill="none"/>
            </g>
          </svg>
        </div>

        <div className="koi koi-2">
          <svg viewBox="0 0 130 60">
            <g className="koi-body">
              <path d="M25 30 Q40 15 70 18 Q100 20 105 30 Q100 40 70 42 Q40 45 25 30 Z" fill="var(--koi-2)" stroke="var(--koi-3)" strokeWidth="1.5"/>
              <ellipse cx="55" cy="28" rx="14" ry="8" fill="var(--koi-1)" opacity=".9"/>
              <ellipse cx="85" cy="30" rx="8" ry="6" fill="var(--koi-1)" opacity=".85"/>
              <path d="M55 18 Q65 8 80 18" fill="var(--koi-1)" stroke="var(--koi-3)" strokeWidth="1" opacity=".85"/>
              <path d="M105 30 Q125 15 128 10 Q120 25 122 30 Q120 35 128 50 Q125 45 105 30 Z" fill="var(--koi-1)" stroke="var(--koi-3)" strokeWidth="1" opacity=".9"/>
              <path d="M45 22 Q40 12 35 15 Q42 22 45 22 Z" fill="var(--koi-1)" opacity=".8"/>
              <path d="M45 38 Q40 48 35 45 Q42 38 45 38 Z" fill="var(--koi-1)" opacity=".8"/>
              <circle cx="35" cy="27" r="2" fill="var(--ink)"/>
              <circle cx="35" cy="33" r="2" fill="var(--ink)"/>
            </g>
          </svg>
        </div>

        <div className="boat">
          <svg viewBox="0 0 180 80">
            <path d="M10 68 Q20 62 30 68 Q40 62 50 68" stroke="var(--water-hi)" strokeWidth="1.5" fill="none" opacity=".6"/>
            <path d="M15 55 Q10 68 25 70 L155 70 Q170 68 165 55 L150 50 L30 50 Z" fill="var(--wood-3)" stroke="var(--wood-2)" strokeWidth="2"/>
            <path d="M30 56 Q60 58 90 56 Q120 58 150 56" stroke="var(--wood-2)" strokeWidth="1" fill="none" opacity=".6"/>
            <path d="M30 62 Q60 64 90 62 Q120 64 150 62" stroke="var(--wood-2)" strokeWidth="1" fill="none" opacity=".6"/>
            <path d="M15 55 Q8 45 18 38" stroke="var(--wood-2)" strokeWidth="3" fill="none" strokeLinecap="round"/>
            <path d="M165 55 Q172 48 168 42" stroke="var(--wood-2)" strokeWidth="3" fill="none" strokeLinecap="round"/>
            <g>
              <ellipse cx="80" cy="30" rx="10" ry="4" fill="var(--paper)" stroke="var(--paper-2)" strokeWidth="1"/>
              <path d="M70 30 L80 22 L90 30" fill="var(--paper)" stroke="var(--paper-2)" strokeWidth="1"/>
              <circle cx="80" cy="38" r="4" fill="#d4a878"/>
              <circle cx="78" cy="37" r=".6" fill="var(--ink)"/>
              <circle cx="82" cy="37" r=".6" fill="var(--ink)"/>
              <path d="M74 42 L80 50 L86 42 L86 55 L74 55 Z" fill="var(--cinnabar)" stroke="var(--cinnabar-2)" strokeWidth="1"/>
              <line x1="70" y1="55" x2="55" y2="45" stroke="var(--wood-2)" strokeWidth="2"/>
              <ellipse cx="52" cy="43" rx="8" ry="3" fill="var(--wood-3)" stroke="var(--wood-2)" strokeWidth="1" transform="rotate(-25 52 43)"/>
              <line x1="76" y1="45" x2="68" y2="50" stroke="#d4a878" strokeWidth="2"/>
            </g>
            <circle cx="155" cy="42" r="5" fill="var(--cinnabar-3)" opacity=".9">
              <animate attributeName="opacity" values=".9;.5;.9" dur="2s" repeatCount="indefinite"/>
            </circle>
            <circle cx="155" cy="42" r="10" fill="var(--cinnabar-3)" opacity=".2"/>
          </svg>
        </div>
      </div>
    </div>
  );
}