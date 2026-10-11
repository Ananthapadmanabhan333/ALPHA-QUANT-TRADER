import React from 'react';

interface LogoProps {
  size?: 'sm' | 'md' | 'lg';
  showText?: boolean;
  className?: string;
}

export const Logo: React.FC<LogoProps> = ({
  size = 'md',
  showText = true,
  className = '',
}) => {
  const sizeMap = {
    sm: 'w-7 h-7',
    md: 'w-9 h-9',
    lg: 'w-14 h-14',
  };

  const textMap = {
    sm: 'text-base',
    md: 'text-lg',
    lg: 'text-2xl',
  };

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <div className={`${sizeMap[size]} flex-shrink-0 relative flex items-center justify-center`}>
        <svg
          viewBox="0 0 100 100"
          className="w-full h-full drop-shadow-[0_0_8px_rgba(212,175,55,0.25)]"
        >
          <defs>
            <linearGradient id="logoGold" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#FBF0D3" />
              <stop offset="35%" stopColor="#D4AF37" />
              <stop offset="70%" stopColor="#AA771C" />
              <stop offset="100%" stopColor="#805A12" />
            </linearGradient>
            <linearGradient id="logoBg" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#181822" />
              <stop offset="100%" stopColor="#08080C" />
            </linearGradient>
          </defs>

          {/* Hexagonal Shield */}
          <polygon
            points="50,4 92,26 92,74 50,96 8,74 8,26"
            fill="url(#logoBg)"
            stroke="url(#logoGold)"
            strokeWidth="2.5"
          />

          {/* Inner Coordinate Ring */}
          <polygon
            points="50,14 82,31 82,69 50,86 18,69 18,31"
            fill="none"
            stroke="rgba(212, 175, 55, 0.25)"
            strokeWidth="1"
            strokeDasharray="2,3"
          />

          {/* Alpha Glyph */}
          <path
            d="M 50,23 L 72,74 L 61,74 L 56,61 L 44,61 L 39,74 L 28,74 Z M 50,39 L 46.5,52 L 53.5,52 Z"
            fill="url(#logoGold)"
          />

          {/* Precision Center Dot */}
          <circle cx="50" cy="50" r="1.5" fill="#FBF0D3" />
        </svg>
      </div>

      {showText && (
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <span className={`font-bold tracking-wider text-alpha-text-primary ${textMap[size]}`}>
              ALPHA
            </span>
            <span className={`font-light tracking-widest text-alpha-gold ${textMap[size]}`}>
              QUANT
            </span>
          </div>
          <span className="text-[10px] uppercase tracking-widest text-alpha-text-muted font-mono -mt-1">
            Foundation Core
          </span>
        </div>
      )}
    </div>
  );
};
