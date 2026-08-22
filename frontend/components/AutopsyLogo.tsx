'use client';

import React from 'react';

interface AutopsyLogoProps {
  size?: 'sm' | 'md' | 'lg';
  showSubtitle?: boolean;
  className?: string;
}

export function AutopsyLogo({ size = 'md', showSubtitle = true, className = '' }: AutopsyLogoProps) {
  const pixelSizes = {
    sm: { container: 28, svg: 18, font: '1rem' },
    md: { container: 34, svg: 22, font: '1.25rem' },
    lg: { container: 44, svg: 28, font: '1.5rem' },
  };

  const currentSize = pixelSizes[size] || pixelSizes.md;

  return (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      {/* Precision Spectral Forensic Aperture Icon */}
      <div
        className="relative flex items-center justify-center shrink-0 rounded-xl bg-slate-900 border border-teal-500/40 shadow-inner group overflow-hidden"
        style={{
          width: currentSize.container,
          height: currentSize.container,
          minWidth: currentSize.container,
          minHeight: currentSize.container,
        }}
      >
        {/* Subtle Grid Backdrop */}
        <div className="absolute inset-0 bg-[radial-gradient(#14b8a6_1px,transparent_1px)] [background-size:6px_6px] opacity-25" />

        {/* Custom SVG Forensic Delta Prism */}
        <svg
          viewBox="0 0 32 32"
          width={currentSize.svg}
          height={currentSize.svg}
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="relative z-10 shrink-0"
          style={{ width: currentSize.svg, height: currentSize.svg, maxWidth: currentSize.svg, maxHeight: currentSize.svg }}
        >
          <defs>
            <linearGradient id="logo-teal-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#2dd4bf" />
              <stop offset="50%" stopColor="#06b6d4" />
              <stop offset="100%" stopColor="#10b981" />
            </linearGradient>
          </defs>

          {/* Outer Target Crosshairs */}
          <circle cx="16" cy="16" r="13" stroke="url(#logo-teal-grad)" strokeWidth="1" strokeOpacity="0.4" strokeDasharray="2 3" />

          {/* Reticle Brackets */}
          <path d="M7 11V7H11" stroke="#2dd4bf" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M21 7H25V11" stroke="#2dd4bf" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M25 21V25H21" stroke="#2dd4bf" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M11 25H7V21" stroke="#2dd4bf" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />

          {/* Central Delta Shift Diamond & Prism */}
          <path
            d="M16 8L23 16L16 24L9 16L16 8Z"
            stroke="url(#logo-teal-grad)"
            strokeWidth="1.5"
            fill="url(#logo-teal-grad)"
            fillOpacity="0.15"
            strokeLinejoin="round"
          />

          {/* Internal Precision Aperture */}
          <circle cx="16" cy="16" r="3" fill="#0f172a" stroke="#2dd4bf" strokeWidth="1.5" />
          <circle cx="16" cy="16" r="1.2" fill="#38bdf8" />
        </svg>
      </div>

      {/* Typography */}
      <div className="flex flex-col leading-tight">
        <div className="flex items-center gap-1.5 leading-none">
          <span
            className="font-black tracking-tight text-slate-900 dark:text-white font-mono"
            style={{ fontSize: currentSize.font }}
          >
            AUTOPSY
          </span>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-black tracking-wider bg-teal-500/15 border border-teal-500/40 text-teal-600 dark:text-teal-400 font-mono shadow-sm">
            .AI
          </span>
        </div>
        {showSubtitle && (
          <span className="text-[10px] font-medium text-slate-500 dark:text-slate-400 tracking-wider uppercase mt-0.5">
            Policy Drift &amp; Forensic Intelligence
          </span>
        )}
      </div>
    </div>
  );
}
