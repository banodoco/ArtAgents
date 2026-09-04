import type {CSSProperties, ReactElement} from 'react';
import {Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

import type {EffectProps} from '@banodoco/timeline-composition/theme-api';

type Params = {
  accent?: string;
  green?: string;
};

type ElementComponentProps = EffectProps<unknown>;

type ComfyNodeDef = {
  u: number;
  x: number;
  y: number;
  w: number;
  header: string;
  inputs: number;
  outputs: number;
  skew: number;
  lines: number;
};

const narrowParams = <T extends object>(raw: unknown): T => {
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    return raw as T;
  }
  return {} as T;
};

const clamp = (value: number, min = 0, max = 1): number => Math.max(min, Math.min(max, value));

const easeOutBack = (t: number): number => {
  const c1 = 1.50158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};

// New path: starts top-left, turns in toward the center, dives to the
// bottom-left corner, wraps around, then continues along the right-side loop.
// The right-side loop is pushed toward the right edge to avoid overlapping
// content in the center-right area.
const noodlePath =
  'M -80 0 C 60 60, 220 180, 360 340 C 520 520, 280 760, 0 1080 C -40 1180, 260 1120, 480 1020 C 680 930, 900 920, 1130 925 C 1500 940, 1720 860, 1680 790 C 1630 720, 1380 520, 1300 330 C 1220 130, 1400 90, 1640 200 C 1840 310, 1900 300, 2000 320 C 2080 340, 2180 260, 2260 200';

// Comfy-esque nodes that drop off along the path at each major anchor point.
// `lines` controls how many obfuscated content rows the node shows.
const comfyNodes: ComfyNodeDef[] = [
  {u: 0.05, x: 90, y: 75, w: 110, header: '#2a9d8f', inputs: 1, outputs: 2, skew: 0, lines: 4},
  {u: 0.20, x: 360, y: 340, w: 152, header: '#264653', inputs: 2, outputs: 1, skew: -4, lines: 8},
  {u: 0.38, x: 0, y: 1040, w: 180, header: '#287271', inputs: 2, outputs: 3, skew: 6, lines: 6},
  {u: 0.48, x: 480, y: 1020, w: 96, header: '#2a9d8f', inputs: 1, outputs: 1, skew: -2, lines: 2},
  {u: 0.60, x: 1130, y: 925, w: 150, header: '#264653', inputs: 2, outputs: 2, skew: 3, lines: 5},
  {u: 0.68, x: 1680, y: 790, w: 168, header: '#287271', inputs: 3, outputs: 2, skew: -5, lines: 8},
  {u: 0.79, x: 1300, y: 330, w: 128, header: '#2a9d8f', inputs: 1, outputs: 2, skew: 4, lines: 3},
  {u: 0.85, x: 1640, y: 200, w: 108, header: '#264653', inputs: 1, outputs: 1, skew: -3, lines: 2},
  {u: 0.93, x: 2000, y: 320, w: 148, header: '#287271', inputs: 2, outputs: 2, skew: 2, lines: 7},
];

const ComfyNode = ({
  node,
  seconds,
  reveal,
}: {
  node: ComfyNodeDef;
  seconds: number;
  reveal: number;
}): ReactElement | null => {
  // Slower, more magical birth (≈0.6s real time).
  const born = clamp((reveal - node.u) / 0.115);
  if (born <= 0) return null;

  const birthProgress = clamp(born);
  const settle = birthProgress < 1;

  // Gentle elastic pop-in instead of a hard plop.
  const pop = settle ? 0.15 + 0.85 * easeOutBack(birthProgress) : 1;
  const scale = pop * (0.94 + 0.06 * Math.sin(seconds * 2.2 + node.u * 12));
  const opacity = Math.min(1, born * 1.2);

  // Soft drift so nodes feel alive once spawned.
  const driftX = 6 * Math.sin(seconds * 0.65 + node.u * 8);
  const driftY = 5 * Math.cos(seconds * 0.55 + node.u * 8);

  const x = node.x + driftX;
  const y = node.y + driftY;
  const rx = 10;
  const bodyColor = '#131b21';
  const portColor = '#7cffbd';
  const portR = 5;
  const headerH = 22;
  const lineHeight = 12;
  const h = headerH + node.lines * lineHeight + 10;
  const portGap = h / (node.inputs + 1);
  const outGap = h / (node.outputs + 1);
  const lineStartY = -h / 2 + headerH + 6;

  // Spawn glow ring expands and fades during birth.
  const glowR = Math.max(node.w, h) * 0.75 * (0.4 + 0.6 * birthProgress);
  const glowOpacity = settle ? (1 - birthProgress) * 0.55 : 0;

  // Shine sweep moves diagonally across the node once during birth.
  const shineOffset = (birthProgress - 0.5) * (node.w + node.h) * 1.4;

  // Sparkle burst travels outward and fades during birth.
  const sparkles = Array.from({length: 5}).map((_, i) => {
    const angle = (i / 5) * Math.PI * 2 + node.u * 3;
    const dist = 24 + 48 * birthProgress;
    return {
      x: Math.cos(angle) * dist,
      y: Math.sin(angle) * dist,
      r: 1.5 + (i % 2) * 1,
      opacity: settle ? (1 - birthProgress) * (0.6 + 0.4 * Math.sin(i * 2)) : 0,
    };
  });

  return (
    <g transform={`translate(${x}, ${y}) rotate(${node.skew}) scale(${scale})`} opacity={opacity}>
      {/* Spawn glow ring */}
      <circle
        cx={0}
        cy={0}
        r={glowR}
        fill="none"
        stroke="#7cffbd"
        strokeWidth={2}
        opacity={glowOpacity}
      />
      <circle
        cx={0}
        cy={0}
        r={glowR * 0.6}
        fill="rgba(124, 255, 189, 0.10)"
        opacity={glowOpacity}
      />

      {/* Sparkle burst */}
      {sparkles.map((s, i) => (
        <circle
          key={`sparkle-${i}`}
          cx={s.x}
          cy={s.y}
          r={s.r}
          fill="#d8fff4"
          opacity={s.opacity}
        />
      ))}

      {/* Node shadow */}
      <rect
        x={-node.w / 2 + 6}
        y={-h / 2 + 8}
        width={node.w}
        height={h}
        rx={rx}
        fill="rgba(0,0,0,0.35)"
      />
      {/* Node body */}
      <rect
        x={-node.w / 2}
        y={-h / 2}
        width={node.w}
        height={h}
        rx={rx}
        fill={bodyColor}
        stroke="rgba(96, 211, 204, 0.42)"
        strokeWidth={1.5}
      />
      {/* Shine sweep mask */}
      {settle && (
        <defs>
          <clipPath id={`shine-clip-${node.u}`}>
            <rect x={-node.w / 2} y={-h / 2} width={node.w} height={h} rx={rx} />
          </clipPath>
        </defs>
      )}
      {settle && (
        <g clipPath={`url(#shine-clip-${node.u})`} opacity={0.55 * (1 - birthProgress)}>
          <rect
            x={shineOffset - node.h * 0.5}
            y={-h}
            width={28}
            height={h * 2}
            fill="rgba(255,255,255,0.55)"
            transform={`rotate(35)`}
          />
        </g>
      )}
      {/* Header bar */}
      <rect
        x={-node.w / 2 + 1}
        y={-h / 2 + 1}
        width={node.w - 2}
        height={headerH - 2}
        rx={rx - 1}
        fill={node.header}
        opacity={0.92}
      />
      {/* Status LED */}
      <circle cx={-node.w / 2 + 14} cy={-h / 2 + 10} r={3} fill="#7cffbd" opacity={0.85} />
      {/* Obfuscated title line */}
      <line
        x1={-node.w / 2 + 26}
        y1={-h / 2 + 10}
        x2={node.w / 2 - 16}
        y2={-h / 2 + 10}
        stroke="rgba(234,255,247,0.55)"
        strokeWidth={3}
        strokeLinecap="round"
      />
      {/* Obfuscated content lines */}
      {Array.from({length: node.lines}).map((_, i) => {
        const lineY = lineStartY + i * lineHeight;
        const widthFactor = 0.55 + 0.35 * Math.sin(i * 1.7 + node.lines);
        return (
          <line
            key={`line-${i}`}
            x1={-node.w / 2 + 16}
            y1={lineY}
            x2={(-node.w / 2 + 16) + (node.w - 40) * widthFactor}
            y2={lineY}
            stroke="rgba(148, 163, 184, 0.26)"
            strokeWidth={3}
            strokeLinecap="round"
          />
        );
      })}
      {/* Input ports */}
      {Array.from({length: node.inputs}).map((_, i) => (
        <circle
          key={`in-${i}`}
          cx={-node.w / 2}
          cy={-h / 2 + (i + 1) * portGap}
          r={portR}
          fill={bodyColor}
          stroke={portColor}
          strokeWidth={2}
        />
      ))}
      {/* Output ports */}
      {Array.from({length: node.outputs}).map((_, i) => (
        <circle
          key={`out-${i}`}
          cx={node.w / 2}
          cy={-h / 2 + (i + 1) * outGap}
          r={portR}
          fill={bodyColor}
          stroke={portColor}
          strokeWidth={2}
        />
      ))}
    </g>
  );
};

export default function VibeComfyAssetOverlay(props: ElementComponentProps): ReactElement {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const params = narrowParams<Params>(props.params);
  const seconds = frame / fps;
  const accent = params.accent ?? '#36d3b0';
  const green = params.green ?? '#7cffbd';

  // Start the path/node animation already at the first node (0.05) so the
  // scene isn't empty at frame 0, then draw the rest slowly so it finishes
  // at 80% of a 10s video (8s). The trailing pulse follows the finish.
  const revealStart = 0.10;
  const revealEnd = 8.0;
  const reveal = clamp(revealStart + (seconds / revealEnd) * (1 - revealStart));
  const tailStart = revealEnd;
  const tail = seconds < tailStart ? 0 : clamp((seconds - tailStart) / 1.5);
  const dashArray = 0.001 + reveal * 0.999;
  const dashOffset = -tail;
  const pulseOpacity = interpolate(seconds, [tailStart + 0.3, tailStart + 0.85], [0, 0.72], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const platformPulse = 1 + 0.012 * Math.sin(seconds * 2.4);
  const titleActivation = clamp((seconds - 1.2) / 4.7);
  const titleScan = 510 + 900 * titleActivation;
  const titleBlueOpacity = interpolate(seconds, [1.0, 2.0, 6.2, 7.1], [0, 0.78, 0.78, 0.36], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none'}}>
      <svg viewBox="0 0 1920 1080" width="1920" height="1080" style={{position: 'absolute', inset: 0}}>
        <defs>
          <linearGradient id="assetNoodleGradient" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#3ce7db" stopOpacity="0.86" />
            <stop offset="55%" stopColor={accent} stopOpacity="0.95" />
            <stop offset="100%" stopColor={green} stopOpacity="0.9" />
          </linearGradient>
          <filter id="assetSoftGlow">
            <feGaussianBlur stdDeviation="8" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <mask id="assetPlatformCutout">
            <rect width="1920" height="1080" fill="white" />
            <rect x="560" y="648" width="800" height="362" rx="90" fill="black" opacity="0.98" />
          </mask>
        </defs>
        <path
          d={noodlePath}
          pathLength={1}
          mask="url(#assetPlatformCutout)"
          fill="none"
          stroke="url(#assetNoodleGradient)"
          strokeWidth="12"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray={`${dashArray} ${1 - dashArray}`}
          strokeDashoffset={dashOffset}
          filter="url(#assetSoftGlow)"
          opacity="0.88"
        />
        {seconds > 5.8 && (
          <path
            d={noodlePath}
            pathLength={1}
            mask="url(#assetPlatformCutout)"
            fill="none"
            stroke={green}
            strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray="0.018 0.10"
            strokeDashoffset={-(seconds - 5.8) * 0.65}
            opacity={pulseOpacity}
          />
        )}
        {comfyNodes.map((node) => (
          <ComfyNode key={node.u} node={node} seconds={seconds} reveal={reveal} />
        ))}
      </svg>

      <Img
        src={staticFile('vibe-comfy-intro/platform-glow.png')}
        style={{
          position: 'absolute',
          left: 575,
          top: 710,
          width: 770,
          height: 235,
          transform: `scale(${platformPulse})`,
          transformOrigin: 'center',
          opacity: 0.34,
          filter: 'drop-shadow(0 12px 24px rgba(0,0,0,0.36))',
        }}
      />
      <Img
        src={staticFile('vibe-comfy-intro/title-vibe-comfy.png')}
        style={{
          position: 'absolute',
          left: 510,
          top: 878,
          width: 900,
          height: 150,
          opacity: 0.92,
          filter: 'drop-shadow(0 0 16px rgba(98,223,236,0.16))',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: 510,
          top: 878,
          width: 900,
          height: 150,
          overflow: 'hidden',
          clipPath: `inset(0 ${Math.max(0, 100 - titleActivation * 100)}% 0 0)`,
          opacity: titleBlueOpacity,
          mixBlendMode: 'screen',
          filter: 'drop-shadow(0 0 20px rgba(67,213,255,0.42)) saturate(1.35)',
        }}
      >
        <Img
          src={staticFile('vibe-comfy-intro/title-vibe-comfy.png')}
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            width: 900,
            height: 150,
            filter: 'brightness(0) saturate(100%) invert(69%) sepia(82%) saturate(2970%) hue-rotate(165deg) brightness(106%) contrast(105%)',
          }}
        />
      </div>
      <div
        style={{
          position: 'absolute',
          left: 550,
          top: 1005,
          width: 820,
          height: 4,
          borderRadius: 999,
          overflow: 'hidden',
          background: 'rgba(83, 130, 150, 0.23)',
          boxShadow: '0 0 14px rgba(45, 215, 255, 0.14)',
        }}
      >
        <div
          style={{
            width: `${titleActivation * 100}%`,
            height: '100%',
            borderRadius: 999,
            background: 'linear-gradient(90deg, #35d8ff, #3b86ff 58%, #7cffbd)',
            boxShadow: '0 0 18px rgba(55, 190, 255, 0.72)',
          }}
        />
      </div>
      <div
        style={{
          position: 'absolute',
          left: titleScan - 9,
          top: 874,
          width: 18,
          height: 142,
          opacity: titleActivation > 0 && titleActivation < 1 ? 0.6 : 0,
          background: 'linear-gradient(180deg, transparent, rgba(69, 215, 255, 0.82), transparent)',
          filter: 'blur(2px)',
        }}
      />
    </div>
  );
}
