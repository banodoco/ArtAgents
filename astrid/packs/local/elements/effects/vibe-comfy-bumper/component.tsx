import type {CSSProperties, ReactElement} from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

import type {EffectProps} from '@banodoco/timeline-composition/theme-api';

type Params = {
  title?: string;
  background?: string;
  accent?: string;
  green?: string;
};

type ElementComponentProps = EffectProps<unknown>;

const narrowParams = <T extends object>(raw: unknown): T => {
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    return raw as T;
  }
  return {} as T;
};

const microAssets = [
  'Prompt',
  'ready',
  'arc',
  '✓',
  'validated',
  'queued',
  'preview',
  'spark',
  'node +',
  'socket',
  'cursor',
  'VC',
];

const positions = [
  [250, 235], [1665, 230], [350, 535], [1540, 500],
  [270, 790], [1625, 780], [585, 185], [1335, 185],
  [545, 865], [1370, 865], [150, 520], [1770, 520],
] as const;

const starts = [0.70, 1.20, 1.80, 2.25, 2.95, 3.65, 4.30, 4.95, 5.55, 6.25, 7.05, 7.70];
const lives = [2.2, 3.0, 4.8, 1.3, 3.6, 2.8, 1.1, 0.75, 2.9, 4.5, 2.2, 1.8];
const scales = [0.74, 0.74, 0.56, 0.52, 0.66, 0.66, 0.76, 0.48, 0.70, 0.54, 0.58, 0.64];
const modes = ['pop', 'slide', 'hold', 'blink', 'rise', 'slide', 'spark', 'spark', 'pop', 'orbit', 'cursor', 'badge'];

const clamp = (value: number, min = 0, max = 1): number => Math.max(min, Math.min(max, value));

const easeOutBack = (t: number): number => {
  const c1 = 1.50158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};

const styles = {
  root: {
    position: 'absolute',
    inset: 0,
    overflow: 'hidden',
    background: 'radial-gradient(circle at 50% 74%, rgba(38, 207, 168, 0.12), transparent 22%), #111519',
    fontFamily: 'Inter, system-ui, sans-serif',
  } satisfies CSSProperties,
  grid: {
    position: 'absolute',
    inset: 0,
    opacity: 0.23,
    backgroundImage:
      'linear-gradient(rgba(148, 163, 184, 0.12) 1px, transparent 1px), linear-gradient(90deg, rgba(148, 163, 184, 0.12) 1px, transparent 1px)',
    backgroundSize: '48px 48px',
  } satisfies CSSProperties,
  platform: {
    position: 'absolute',
    left: 760,
    top: 700,
    width: 400,
    height: 104,
    borderRadius: '50%',
    background: 'radial-gradient(ellipse at center, rgba(61, 220, 177, 0.18), rgba(61, 220, 177, 0.045) 46%, transparent 72%)',
    border: '1px solid rgba(84, 241, 191, 0.20)',
    boxShadow: '0 0 55px rgba(53, 209, 172, 0.10)',
  } satisfies CSSProperties,
  title: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 110,
    textAlign: 'center',
    color: 'rgba(245, 248, 252, 0.92)',
    fontSize: 52,
    lineHeight: 1,
    fontWeight: 760,
    letterSpacing: 7,
    textShadow: '0 0 22px rgba(54, 211, 176, 0.25)',
  } satisfies CSSProperties,
};

const Asset = ({i, seconds}: {i: number; seconds: number}): ReactElement | null => {
  const local = seconds - starts[i];
  if (local < 0 || local > lives[i]) return null;
  const fadeIn = clamp(local / 0.26);
  const fadeOut = clamp((lives[i] - local) / 0.34);
  let opacity = Math.min(fadeIn, fadeOut);
  if (opacity <= 0) return null;

  let [x, y] = positions[i];
  let scale = scales[i];
  if (local < 0.34) scale *= 0.35 + 0.65 * easeOutBack(clamp(local / 0.34));
  const mode = modes[i];
  if (mode === 'slide') x += (1 - fadeIn) * (x < 960 ? 95 : -95);
  if (mode === 'rise') y += (1 - fadeIn) * 60;
  if (mode === 'blink') opacity *= 0.52 + 0.48 * (0.5 + 0.5 * Math.sin(seconds * 11));
  if (mode === 'spark') scale *= 0.82 + 0.28 * Math.sin(seconds * 9 + i);
  if (mode === 'orbit') {
    x += 30 * Math.sin(seconds * 0.85);
    y += 22 * Math.cos(seconds * 0.85);
  }
  if (mode === 'cursor') {
    const u = clamp(local / 1.75);
    x += 125 * u;
    y -= 55 * Math.sin(u * Math.PI);
  }
  if (mode === 'badge') y += 8 * Math.sin(seconds * 1.8);
  if (mode === 'pop') y += 3 * Math.sin(seconds * 2.4 + i);

  const label = microAssets[i];
  const isPill = ['validated', 'queued', 'ready', 'node +'].includes(label);
  const isBadge = label === '✓' || label === 'VC';
  const isArc = label === 'arc';
  const isSpark = label === 'spark';
  const isSocket = label === 'socket';
  const isCursor = label === 'cursor';
  const isPreview = label === 'preview';

  const baseStyle: CSSProperties = {
    position: 'absolute',
    left: x,
    top: y,
    transform: `translate(-50%, -50%) scale(${scale})`,
    transformOrigin: 'center',
    opacity,
    filter: 'drop-shadow(5px 7px 7px rgba(0,0,0,0.22))',
    color: '#eafff7',
    fontFamily: 'Inter, system-ui, sans-serif',
  };

  if (isArc) {
    return (
      <svg width="230" height="120" viewBox="0 0 230 120" style={baseStyle}>
        <path d="M 18 86 C 70 16, 152 18, 210 72" fill="none" stroke="#4fdcca" strokeWidth="10" strokeLinecap="round" />
        <path d="M 18 86 C 70 16, 152 18, 210 72" fill="none" stroke="#d8fff4" strokeWidth="3" strokeLinecap="round" opacity="0.9" />
        <circle cx="18" cy="86" r="9" fill="#7cffbd" />
        <circle cx="210" cy="72" r="9" fill="#7cffbd" />
      </svg>
    );
  }

  if (isSpark) {
    return (
      <svg width="120" height="120" viewBox="0 0 120 120" style={baseStyle}>
        <path d="M60 12 L70 48 L108 60 L70 72 L60 108 L50 72 L12 60 L50 48 Z" fill="#7cffbd" opacity="0.9" />
        <circle cx="60" cy="60" r="30" fill="none" stroke="#53dbc8" strokeWidth="3" opacity="0.55" />
      </svg>
    );
  }

  if (isSocket) {
    return (
      <svg width="150" height="80" viewBox="0 0 150 80" style={baseStyle}>
        <circle cx="40" cy="40" r="18" fill="#151c22" stroke="#5edbc8" strokeWidth="5" />
        <circle cx="110" cy="40" r="18" fill="#151c22" stroke="#7cffbd" strokeWidth="5" />
        <path d="M58 40 H92" stroke="#86fff0" strokeWidth="6" strokeLinecap="round" />
      </svg>
    );
  }

  if (isCursor) {
    return (
      <svg width="130" height="115" viewBox="0 0 130 115" style={baseStyle}>
        <path d="M20 12 L102 64 L66 70 L50 104 Z" fill="#dffdf7" stroke="#48d9ca" strokeWidth="4" />
        <path d="M8 18 C 20 6, 42 2, 56 8" fill="none" stroke="#7cffbd" strokeWidth="4" strokeLinecap="round" opacity="0.62" />
      </svg>
    );
  }

  if (isPreview) {
    return (
      <div
        style={{
          ...baseStyle,
          width: 178,
          height: 112,
          borderRadius: 14,
          border: '1px solid rgba(112, 231, 205, 0.55)',
          background: 'linear-gradient(135deg, #17222a, #263947 52%, #f2a65a)',
          boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.08)',
        }}
      />
    );
  }

  if (isBadge) {
    return (
      <div
        style={{
          ...baseStyle,
          minWidth: 72,
          height: 72,
          borderRadius: 20,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: label === '✓' ? 42 : 30,
          fontWeight: 820,
          background: label === '✓' ? 'rgba(37, 179, 125, 0.92)' : 'rgba(20, 28, 36, 0.92)',
          border: '1px solid rgba(124, 255, 189, 0.45)',
        }}
      >
        {label}
      </div>
    );
  }

  return (
    <div
      style={{
        ...baseStyle,
        minWidth: isPill ? 150 : 190,
        height: isPill ? 54 : 92,
        boxSizing: 'border-box',
        padding: isPill ? '0 20px' : '14px 18px',
        borderRadius: isPill ? 999 : 16,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 10,
        background: isPill ? 'rgba(18, 29, 35, 0.92)' : 'rgba(17, 24, 32, 0.92)',
        border: `1px solid ${label === 'ready' ? 'rgba(124,255,189,0.68)' : 'rgba(96, 211, 204, 0.44)'}`,
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.08)',
        fontSize: isPill ? 24 : 26,
        fontWeight: 720,
      }}
    >
      {!isPill && <span style={{width: 12, height: 12, borderRadius: 6, background: '#7cffbd'}} />}
      {label}
    </div>
  );
};

export default function VibeComfyBumper(props: ElementComponentProps): ReactElement {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const params = narrowParams<Params>(props.params);
  const seconds = frame / fps;
  const title = params.title ?? 'VIBE COMFY';
  const accent = params.accent ?? '#36d3b0';
  const green = params.green ?? '#7cffbd';

  const reveal = clamp((seconds - 0.55) / 5.4);
  const tail = seconds < 5.25 ? 0 : clamp((seconds - 5.25) / 3.6);
  const dashArray = 0.001 + reveal * 0.999;
  const dashOffset = -tail;
  const pulseOpacity = interpolate(seconds, [5.9, 6.4], [0, 0.75], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div style={{...styles.root, background: params.background ?? styles.root.background}}>
      <div style={styles.grid} />
      <svg viewBox="0 0 1920 1080" width="1920" height="1080" style={{position: 'absolute', inset: 0}}>
        <defs>
          <linearGradient id="noodleGradient" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#3ce7db" stopOpacity="0.85" />
            <stop offset="55%" stopColor={accent} stopOpacity="0.95" />
            <stop offset="100%" stopColor={green} stopOpacity="0.9" />
          </linearGradient>
          <filter id="softGlow">
            <feGaussianBlur stdDeviation="8" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <mask id="platformCutout">
            <rect width="1920" height="1080" fill="white" />
            <rect x="600" y="620" width="720" height="395" rx="80" fill="black" opacity="0.96" />
          </mask>
        </defs>
        <path
          d="M -180 455 C 130 310, 390 385, 520 610 S 350 805, 620 930 S 1130 925, 1505 795 S 1190 330, 1445 205 S 1775 310, 2085 225"
          pathLength={1}
          mask="url(#platformCutout)"
          fill="none"
          stroke="url(#noodleGradient)"
          strokeWidth="13"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray={`${dashArray} ${1 - dashArray}`}
          strokeDashoffset={dashOffset}
          filter="url(#softGlow)"
          opacity="0.95"
        />
        {seconds > 5.9 && (
          <path
            d="M -180 455 C 130 310, 390 385, 520 610 S 350 805, 620 930 S 1130 925, 1505 795 S 1190 330, 1445 205 S 1775 310, 2085 225"
            pathLength={1}
            mask="url(#platformCutout)"
            fill="none"
            stroke={green}
            strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray="0.018 0.10"
            strokeDashoffset={-(seconds - 5.9) * 0.65}
            opacity={pulseOpacity}
          />
        )}
      </svg>
      <div style={styles.platform} />
      <div style={styles.title}>{title}</div>
      {microAssets.map((_, i) => <Asset key={i} i={i} seconds={seconds} />)}
    </div>
  );
}
