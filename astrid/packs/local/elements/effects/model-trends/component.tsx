import type {CSSProperties, ReactElement} from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

import {
  type Anchor,
  anchorPosition,
  fadeOpacity,
  normalizeEffects,
  slideTransform,
} from '../_shared/clip-effects';
import {
  type ElementComponentProps,
  narrowParams,
} from '../../../../rendering/elements/_shared/contracts';

// Local-pack ModelTrends: Remotion-driven port of the Banodoco /1m
// "Models Come and Go" stacked-area chart.
//
// Recharts is not bundled in this Remotion project, so the chart is
// hand-rolled with SVG paths. Visually equivalent: stacked areas,
// linearGradient fills, dotted grid, six-tick X axis, percent Y axis.
//
// Animation is purely frame-driven — no useState, no rAF, no
// IntersectionObserver. The dataset's `totalDataFrames` are mapped
// linearly onto the clip's playback duration.

type ChartParams = {
  anchor?: Anchor;
  offsetX?: number;
  offsetY?: number;
  width?: number;
  height?: number;
  padding?: number | string;
  borderRadius?: number | string;
  border?: string;
  background?: string;
  backdropFilter?: string;
  boxShadow?: string;
  accent?: string;
};

// ============ Constants — colors derived from src/index.css =========
// The website uses CSS variables (--wrapped-model-*). Those don't
// exist inside the Remotion bundle, so we hardcode the values copied
// directly from banodoco-website/src/index.css lines 27-34.

type ModelKey = 'sd' | 'animatediff' | 'flux' | 'wan' | 'cogvideo' | 'hunyuan' | 'ltx';

const MODEL_COLORS: Record<ModelKey, {stroke: string; name: string}> = {
  sd:          {stroke: '#3B82F6', name: 'Stable Diffusion'},
  animatediff: {stroke: '#F97316', name: 'AnimateDiff'},
  flux:        {stroke: '#A855F7', name: 'Flux'},
  wan:         {stroke: '#22C55E', name: 'Wan'},
  cogvideo:    {stroke: '#EC4899', name: 'CogVideoX'},
  hunyuan:     {stroke: '#EAB308', name: 'HunyuanVideo'},
  ltx:         {stroke: '#06B6D4', name: 'LTX'},
};

const MODEL_KEYS: ModelKey[] = ['sd', 'animatediff', 'flux', 'wan', 'cogvideo', 'hunyuan', 'ltx'];

const CHART_COLORS = {
  axisAndTicks: '#666',
  grid: '#333',
} as const;

// ============ Baked-in dataset (from Wrapped/constants.ts) ============

type ModelTrend = {month: string} & Record<ModelKey, number>;
type CumulativeDataPoint = {date: string; cumulative: number};

// Sourced verbatim from banodoco-website/public/wrapped/data.json
// (30 monthly model-trend points, ending 2026-01).
const MODEL_TRENDS: ModelTrend[] = [
  {month: '2023-08', sd: 0,    animatediff: 100,  flux: 0,    wan: 0,    cogvideo: 0,    hunyuan: 0,    ltx: 0},
  {month: '2023-09', sd: 0,    animatediff: 100,  flux: 0,    wan: 0,    cogvideo: 0,    hunyuan: 0,    ltx: 0},
  {month: '2023-10', sd: 0,    animatediff: 100,  flux: 0,    wan: 0,    cogvideo: 0,    hunyuan: 0,    ltx: 0},
  {month: '2023-11', sd: 63.5, animatediff: 36.5, flux: 0,    wan: 0,    cogvideo: 0,    hunyuan: 0,    ltx: 0},
  {month: '2023-12', sd: 21.6, animatediff: 78.4, flux: 0,    wan: 0,    cogvideo: 0,    hunyuan: 0,    ltx: 0},
  {month: '2024-01', sd: 33.9, animatediff: 66.1, flux: 0,    wan: 0,    cogvideo: 0,    hunyuan: 0,    ltx: 0},
  {month: '2024-02', sd: 2.3,  animatediff: 97.7, flux: 0,    wan: 0,    cogvideo: 0,    hunyuan: 0,    ltx: 0},
  {month: '2024-03', sd: 2.5,  animatediff: 97.5, flux: 0,    wan: 0,    cogvideo: 0,    hunyuan: 0,    ltx: 0},
  {month: '2024-04', sd: 4.6,  animatediff: 95.4, flux: 0,    wan: 0,    cogvideo: 0,    hunyuan: 0,    ltx: 0},
  {month: '2024-05', sd: 1.8,  animatediff: 98.2, flux: 0,    wan: 0,    cogvideo: 0,    hunyuan: 0,    ltx: 0},
  {month: '2024-06', sd: 70.9, animatediff: 27,   flux: 0,    wan: 0,    cogvideo: 0,    hunyuan: 2.1,  ltx: 0},
  {month: '2024-07', sd: 16.1, animatediff: 81,   flux: 0,    wan: 0,    cogvideo: 0,    hunyuan: 2.9,  ltx: 0},
  {month: '2024-08', sd: 0.2,  animatediff: 1.5,  flux: 86.1, wan: 0,    cogvideo: 12.2, hunyuan: 0.1,  ltx: 0},
  {month: '2024-09', sd: 0,    animatediff: 1.8,  flux: 37.4, wan: 0,    cogvideo: 60.6, hunyuan: 0.1,  ltx: 0},
  {month: '2024-10', sd: 2,    animatediff: 2.8,  flux: 14.7, wan: 0,    cogvideo: 80.5, hunyuan: 0,    ltx: 0},
  {month: '2024-11', sd: 0.4,  animatediff: 0.6,  flux: 6.9,  wan: 0,    cogvideo: 77,   hunyuan: 0,    ltx: 15},
  {month: '2024-12', sd: 0,    animatediff: 0.3,  flux: 1.5,  wan: 0,    cogvideo: 6,    hunyuan: 82.7, ltx: 9.5},
  {month: '2025-01', sd: 0.6,  animatediff: 2.8,  flux: 2.9,  wan: 0,    cogvideo: 5.7,  hunyuan: 80.6, ltx: 7.5},
  {month: '2025-02', sd: 0.1,  animatediff: 1,    flux: 1.9,  wan: 28.5, cogvideo: 0.8,  hunyuan: 66.1, ltx: 1.8},
  {month: '2025-03', sd: 0,    animatediff: 1,    flux: 3.2,  wan: 68.1, cogvideo: 0.1,  hunyuan: 22.9, ltx: 4.6},
  {month: '2025-04', sd: 0,    animatediff: 0.3,  flux: 3.6,  wan: 77.9, cogvideo: 0,    hunyuan: 16.4, ltx: 1.7},
  {month: '2025-05', sd: 0,    animatediff: 0.2,  flux: 2.9,  wan: 69.9, cogvideo: 0,    hunyuan: 12.6, ltx: 14.5},
  {month: '2025-06', sd: 0.2,  animatediff: 0.2,  flux: 7.9,  wan: 86,   cogvideo: 0,    hunyuan: 4.9,  ltx: 0.7},
  {month: '2025-07', sd: 0.2,  animatediff: 0.1,  flux: 5.6,  wan: 92.4, cogvideo: 0,    hunyuan: 1.1,  ltx: 0.7},
  {month: '2025-08', sd: 0.1,  animatediff: 0.1,  flux: 2,    wan: 97.3, cogvideo: 0,    hunyuan: 0.5,  ltx: 0.1},
  {month: '2025-09', sd: 0,    animatediff: 0.1,  flux: 1.2,  wan: 96,   cogvideo: 0,    hunyuan: 2.5,  ltx: 0.1},
  {month: '2025-10', sd: 0,    animatediff: 0,    flux: 0.4,  wan: 98,   cogvideo: 0,    hunyuan: 0.8,  ltx: 0.7},
  {month: '2025-11', sd: 0,    animatediff: 0.1,  flux: 10.1, wan: 73.4, cogvideo: 0,    hunyuan: 15.9, ltx: 0.5},
  {month: '2025-12', sd: 0.1,  animatediff: 0,    flux: 2.3,  wan: 95.3, cogvideo: 0,    hunyuan: 1.5,  ltx: 0.7},
  {month: '2026-01', sd: 0,    animatediff: 0.1,  flux: 3.1,  wan: 13,   cogvideo: 0,    hunyuan: 0.2,  ltx: 83.6},
];

// 130 daily-ish cumulative-message points (verbatim from data.json).
const CUMULATIVE_MESSAGES: CumulativeDataPoint[] = [
  {date: '2023-08-14', cumulative: 163},
  {date: '2023-08-21', cumulative: 622},
  {date: '2023-08-28', cumulative: 4017},
  {date: '2023-09-04', cumulative: 9650},
  {date: '2023-09-11', cumulative: 12997},
  {date: '2023-09-18', cumulative: 18193},
  {date: '2023-09-25', cumulative: 27237},
  {date: '2023-10-02', cumulative: 35129},
  {date: '2023-10-09', cumulative: 40546},
  {date: '2023-10-16', cumulative: 46594},
  {date: '2023-10-23', cumulative: 53200},
  {date: '2023-10-30', cumulative: 59654},
  {date: '2023-11-06', cumulative: 65173},
  {date: '2023-11-13', cumulative: 73676},
  {date: '2023-11-20', cumulative: 80861},
  {date: '2023-11-27', cumulative: 91082},
  {date: '2023-12-04', cumulative: 100360},
  {date: '2023-12-11', cumulative: 107492},
  {date: '2023-12-18', cumulative: 113838},
  {date: '2023-12-25', cumulative: 120027},
  {date: '2024-01-01', cumulative: 125130},
  {date: '2024-01-08', cumulative: 130168},
  {date: '2024-01-15', cumulative: 135972},
  {date: '2024-01-22', cumulative: 140860},
  {date: '2024-01-29', cumulative: 145622},
  {date: '2024-02-05', cumulative: 150652},
  {date: '2024-02-12', cumulative: 156798},
  {date: '2024-02-19', cumulative: 163551},
  {date: '2024-02-26', cumulative: 171487},
  {date: '2024-03-04', cumulative: 178832},
  {date: '2024-03-11', cumulative: 184600},
  {date: '2024-03-18', cumulative: 188716},
  {date: '2024-03-25', cumulative: 193045},
  {date: '2024-04-01', cumulative: 197688},
  {date: '2024-04-08', cumulative: 202079},
  {date: '2024-04-15', cumulative: 206078},
  {date: '2024-04-22', cumulative: 209761},
  {date: '2024-04-29', cumulative: 213809},
  {date: '2024-05-06', cumulative: 217746},
  {date: '2024-05-13', cumulative: 221765},
  {date: '2024-05-20', cumulative: 224227},
  {date: '2024-05-27', cumulative: 226373},
  {date: '2024-06-03', cumulative: 231056},
  {date: '2024-06-10', cumulative: 234139},
  {date: '2024-06-17', cumulative: 241329},
  {date: '2024-06-24', cumulative: 246136},
  {date: '2024-07-01', cumulative: 249723},
  {date: '2024-07-08', cumulative: 253932},
  {date: '2024-07-15', cumulative: 258073},
  {date: '2024-07-22', cumulative: 261086},
  {date: '2024-07-29', cumulative: 264885},
  {date: '2024-08-05', cumulative: 272561},
  {date: '2024-08-12', cumulative: 278819},
  {date: '2024-08-19', cumulative: 289370},
  {date: '2024-08-26', cumulative: 294604},
  {date: '2024-09-02', cumulative: 301967},
  {date: '2024-09-09', cumulative: 305383},
  {date: '2024-09-16', cumulative: 308296},
  {date: '2024-09-23', cumulative: 312715},
  {date: '2024-09-30', cumulative: 314962},
  {date: '2024-10-07', cumulative: 318533},
  {date: '2024-10-14', cumulative: 321133},
  {date: '2024-10-21', cumulative: 323262},
  {date: '2024-10-28', cumulative: 327505},
  {date: '2024-11-04', cumulative: 330297},
  {date: '2024-11-11', cumulative: 334451},
  {date: '2024-11-18', cumulative: 340487},
  {date: '2024-11-25', cumulative: 347078},
  {date: '2024-12-02', cumulative: 352825},
  {date: '2024-12-09', cumulative: 365719},
  {date: '2024-12-16', cumulative: 374261},
  {date: '2024-12-23', cumulative: 384124},
  {date: '2024-12-30', cumulative: 387097},
  {date: '2025-01-06', cumulative: 393461},
  {date: '2025-01-13', cumulative: 401927},
  {date: '2025-01-20', cumulative: 409274},
  {date: '2025-01-27', cumulative: 415067},
  {date: '2025-02-03', cumulative: 422500},
  {date: '2025-02-10', cumulative: 428303},
  {date: '2025-02-17', cumulative: 435858},
  {date: '2025-02-24', cumulative: 447371},
  {date: '2025-03-03', cumulative: 467879},
  {date: '2025-03-10', cumulative: 488476},
  {date: '2025-03-17', cumulative: 501418},
  {date: '2025-03-24', cumulative: 511550},
  {date: '2025-03-31', cumulative: 523276},
  {date: '2025-04-07', cumulative: 533724},
  {date: '2025-04-14', cumulative: 540376},
  {date: '2025-04-21', cumulative: 552746},
  {date: '2025-04-28', cumulative: 566394},
  {date: '2025-05-05', cumulative: 574628},
  {date: '2025-05-12', cumulative: 584894},
  {date: '2025-05-19', cumulative: 598195},
  {date: '2025-05-26', cumulative: 609936},
  {date: '2025-06-02', cumulative: 620795},
  {date: '2025-06-09', cumulative: 631499},
  {date: '2025-06-16', cumulative: 639763},
  {date: '2025-06-23', cumulative: 649216},
  {date: '2025-06-30', cumulative: 660684},
  {date: '2025-07-07', cumulative: 670275},
  {date: '2025-07-14', cumulative: 677256},
  {date: '2025-07-21', cumulative: 686443},
  {date: '2025-07-28', cumulative: 701775},
  {date: '2025-08-04', cumulative: 727054},
  {date: '2025-08-11', cumulative: 744601},
  {date: '2025-08-18', cumulative: 758630},
  {date: '2025-08-25', cumulative: 776954},
  {date: '2025-09-01', cumulative: 789106},
  {date: '2025-09-08', cumulative: 798532},
  {date: '2025-09-15', cumulative: 807843},
  {date: '2025-09-22', cumulative: 821597},
  {date: '2025-09-29', cumulative: 835396},
  {date: '2025-10-06', cumulative: 851240},
  {date: '2025-10-13', cumulative: 862230},
  {date: '2025-10-20', cumulative: 872386},
  {date: '2025-10-27', cumulative: 884261},
  {date: '2025-11-03', cumulative: 893862},
  {date: '2025-11-10', cumulative: 900135},
  {date: '2025-11-17', cumulative: 908865},
  {date: '2025-11-24', cumulative: 918387},
  {date: '2025-12-01', cumulative: 935231},
  {date: '2025-12-08', cumulative: 946655},
  {date: '2025-12-15', cumulative: 958257},
  {date: '2025-12-22', cumulative: 968856},
  {date: '2025-12-29', cumulative: 977363},
  {date: '2026-01-05', cumulative: 985967},
  {date: '2026-01-12', cumulative: 1011276},
  {date: '2026-01-19', cumulative: 1027431},
  {date: '2026-01-26', cumulative: 1041294},
  {date: '2026-01-31', cumulative: 1049874},
];

// ============ Utilities (ported from ModelTrends.tsx) ============

function normalizeData(data: ModelTrend[]): ModelTrend[] {
  return data.map((point) => {
    const total = MODEL_KEYS.reduce((sum, k) => sum + (point[k] || 0), 0);
    if (total === 0 || Math.abs(total - 100) < 0.01) return point;
    const out: ModelTrend = {...point};
    MODEL_KEYS.forEach((k) => {
      out[k] = (point[k] || 0) * (100 / total);
    });
    return out;
  });
}

function formatMonth(monthStr: string): string {
  const [year, month] = monthStr.split('-');
  const date = new Date(parseInt(year, 10), parseInt(month, 10) - 1);
  return date.toLocaleDateString('en-US', {month: 'short', year: 'numeric'});
}

function getVisibleTickIndices(totalCount: number, maxTicks: number = 6): Set<number> {
  if (totalCount <= maxTicks) {
    return new Set(Array.from({length: totalCount}, (_, i) => i));
  }
  const indices = new Set<number>();
  const lastIndex = totalCount - 1;
  indices.add(0);
  indices.add(lastIndex);
  const remaining = maxTicks - 2;
  const step = lastIndex / (remaining + 1);
  for (let i = 1; i <= remaining; i++) {
    indices.add(Math.round(step * i));
  }
  return indices;
}

// Convert "YYYY-MM" or "YYYY-MM-DD" to a JS time for ordering / lookup.
function toTime(dateStr: string): number {
  const parts = dateStr.split('-').map((s) => parseInt(s, 10));
  return new Date(parts[0], (parts[1] ?? 1) - 1, parts[2] ?? 1).getTime();
}

// ============ SVG path builder for stacked areas ============

type Point = {x: number; y: number};

/** Straight-line polyline between points. No smoothing — Catmull-Rom can
 *  push control-point Y values outside the chart's [0, 100%] bounds at
 *  sharp transitions (e.g. a value going from 0 to 80 across one cell at
 *  the reveal leading edge). Linear segments stay strictly within the
 *  data envelope — no spurious overshoot above 100% or below 0%. */
function buildPolylinePath(points: Point[]): string {
  if (points.length === 0) return '';
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 1; i < points.length; i++) {
    d += ` L ${points[i].x} ${points[i].y}`;
  }
  return d;
}

// ============ Main component ============

export default function ModelTrends(
  props: ElementComponentProps,
): ReactElement | null {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const clip = props.clip;
  const params = narrowParams<ChartParams>(clip.params ?? props.params);
  const effects = normalizeEffects(clip.effects);

  const sourceDuration =
    typeof clip.hold === 'number'
      ? clip.hold
      : (clip.to ?? 0) - (clip.from ?? 0);
  const speed = clip.speed ?? 1;
  const durationFrames = Math.max(1, Math.round((sourceDuration / speed) * fps));
  const opacity = fadeOpacity(effects, frame, durationFrames, fps);
  const transform = slideTransform(effects, frame, durationFrames, fps);

  const useManual =
    clip.x !== undefined || clip.y !== undefined ||
    clip.width !== undefined || clip.height !== undefined;

  const anchor: Anchor = params.anchor ?? 'top-right';
  const offsetX = params.offsetX ?? 60;
  const offsetY = params.offsetY ?? 60;
  const widthPx = params.width ?? clip.width ?? 540;
  const heightPx = params.height ?? clip.height ?? 420;

  const positionStyle: CSSProperties = useManual
    ? {position: 'absolute', left: clip.x, top: clip.y, width: clip.width, height: clip.height}
    : {...anchorPosition(anchor, offsetX, offsetY), width: widthPx, height: heightPx};

  const positionTransform = positionStyle.transform as string | undefined;
  const mergedTransform = [positionTransform, transform]
    .filter((t): t is string => Boolean(t))
    .join(' ');

  const containerStyle: CSSProperties = {
    ...positionStyle,
    opacity,
    transform: mergedTransform || undefined,
    pointerEvents: 'none',
    boxSizing: 'border-box',
    background: params.background ?? 'rgba(8, 8, 14, 0.86)',
    padding: params.padding ?? '20px',
    borderRadius: params.borderRadius ?? '14px',
    border: params.border ?? '1px solid rgba(255, 255, 255, 0.08)',
    backdropFilter: params.backdropFilter,
    WebkitBackdropFilter: params.backdropFilter,
    boxShadow: params.boxShadow,
    color: '#fff',
    fontFamily: 'Inter, system-ui, sans-serif',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  };

  const accent = params.accent ?? '#9F1C1C';

  // ====== Frame -> continuous chart progress ======
  // Reserve the fade-out window so the chart finishes traversing the
  // dataset before opacity starts dropping; otherwise the final months
  // fly past in the dim tail of the clip.
  const fadeOutFrames = Math.round((effects.fade_out ?? 0) * fps);
  const animatableFrames = Math.max(1, durationFrames - fadeOutFrames);

  const normalized = normalizeData(MODEL_TRENDS);
  const totalDataFrames = normalized.length;

  // chartProgress is a smooth 0..1 over the animatable portion of the clip.
  const chartProgress = Math.min(1, Math.max(0, frame / animatableFrames));

  // monthFloatIndex sweeps continuously across the [0, totalDataFrames-1]
  // domain; lerpT is the fractional position between the two bracketing months.
  const monthFloatIndex = chartProgress * (totalDataFrames - 1);
  const monthIdxLow = Math.floor(monthFloatIndex);
  const monthIdxHigh = Math.min(totalDataFrames - 1, monthIdxLow + 1);
  const lerpT = monthFloatIndex - monthIdxLow;

  // Per-frame stacked-area "head": every month up to monthIdxLow is shown
  // verbatim, the bracketing month is interpolated by lerpT, and any later
  // months collapse onto that interpolated head so the area smoothly grows.
  const interpolatedHead: ModelTrend = (() => {
    const a = normalized[monthIdxLow];
    const b = normalized[monthIdxHigh];
    const out: ModelTrend = {month: a.month, sd: 0, animatediff: 0, flux: 0, wan: 0, cogvideo: 0, hunyuan: 0, ltx: 0};
    MODEL_KEYS.forEach((k) => {
      out[k] = (a[k] || 0) * (1 - lerpT) + (b[k] || 0) * lerpT;
    });
    return out;
  })();

  // Reveal-left-to-right: months at or before monthIdxLow show their real
  // (normalized) values, the bracketing month is interpolated, and any
  // FUTURE months are zeroed out. This is what makes the stacked area
  // visibly fill in over time instead of being pre-rendered across the
  // whole X-axis. Mirrors the website's `displayData` reveal pattern.
  const zeroedRow = (month: string): ModelTrend => ({
    month,
    sd: 0, animatediff: 0, flux: 0, wan: 0, cogvideo: 0, hunyuan: 0, ltx: 0,
  });
  const displayData: ModelTrend[] = normalized.map((point, idx) => {
    if (idx <= monthIdxLow) return point;
    if (idx === monthIdxHigh) return interpolatedHead;
    return zeroedRow(point.month);
  });

  const labelMonth = normalized[Math.min(totalDataFrames - 1, Math.round(monthFloatIndex))].month;

  // Continuous cumulative-message count, derived from the same chartProgress
  // so it visibly ticks every video frame.
  const cumulativeNow = (() => {
    const series = CUMULATIVE_MESSAGES;
    const t0 = toTime(series[0].date);
    const t1 = toTime(series[series.length - 1].date);
    const targetT = t0 + (t1 - t0) * chartProgress;
    if (targetT <= t0) return series[0].cumulative;
    if (targetT >= t1) return series[series.length - 1].cumulative;
    for (let i = 0; i < series.length - 1; i++) {
      const ta = toTime(series[i].date);
      const tb = toTime(series[i + 1].date);
      if (targetT >= ta && targetT <= tb) {
        const u = (targetT - ta) / (tb - ta);
        return series[i].cumulative + (series[i + 1].cumulative - series[i].cumulative) * u;
      }
    }
    return series[series.length - 1].cumulative;
  })();

  // ====== Chart geometry ======
  // SVG inner area (excluding margins/axes) — mirrors the recharts margin.
  const innerW = widthPx - (typeof params.padding === 'number' ? params.padding * 2 : 40);
  // Title + counter rows take vertical space; chart fills the remainder.
  const titleRowH = 36;
  const counterRowH = 64;
  const innerH = heightPx - (typeof params.padding === 'number' ? params.padding * 2 : 40) - titleRowH - counterRowH;

  const margin = {top: 28, right: 24, bottom: 24, left: 36};
  const plotW = Math.max(0, innerW - margin.left - margin.right);
  const plotH = Math.max(0, innerH - margin.top - margin.bottom);

  // Compute stacked points per series. Stacked order = MODEL_KEYS order
  // (same as the website's `<Area>` declaration order).
  const xFor = (i: number) => margin.left + (plotW * i) / (displayData.length - 1);
  const yFor = (pct: number) => margin.top + plotH * (1 - pct / 100);

  const stackedSeries: {key: ModelKey; topPoints: Point[]; bottomPoints: Point[]; stroke: string}[] = [];
  const cumulative: number[] = displayData.map(() => 0);
  for (const key of MODEL_KEYS) {
    const bottomPoints: Point[] = displayData.map((row, i) => ({
      x: xFor(i),
      y: yFor(cumulative[i]),
    }));
    const topPoints: Point[] = displayData.map((row, i) => {
      cumulative[i] = cumulative[i] + (row[key] || 0);
      return {x: xFor(i), y: yFor(cumulative[i])};
    });
    stackedSeries.push({
      key,
      topPoints,
      bottomPoints,
      stroke: MODEL_COLORS[key].stroke,
    });
  }

  // X-axis tick selection (max 6, always include first+last)
  const tickIdx = getVisibleTickIndices(displayData.length, 6);

  // Y axis ticks at 0, 25, 50, 75, 100
  const yTicks = [0, 25, 50, 75, 100];

  // ====== Render ======
  return (
    <div style={containerStyle}>
      {/* Title row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 12,
          marginBottom: 8,
          height: titleRowH,
        }}
      >
        <div style={{display: 'flex', alignItems: 'center', minWidth: 0}}>
          <div
            style={{
              fontSize: 13,
              color: 'rgba(255,255,255,0.6)',
              letterSpacing: '0.02em',
            }}
          >
            Messages by model over the past {MODEL_TRENDS.length} months
          </div>
        </div>
        {/* "Until <Month>" pill */}
        <div
          style={{
            background: 'rgba(0,0,0,0.55)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 6,
            padding: '4px 10px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-start',
            lineHeight: 1.1,
            flexShrink: 0,
          }}
        >
          <span
            style={{
              fontSize: 9,
              letterSpacing: '0.18em',
              textTransform: 'uppercase',
              color: 'rgba(255,255,255,0.45)',
            }}
          >
            Until
          </span>
          <span
            style={{
              fontSize: 13,
              fontFamily: 'ui-monospace, "SF Mono", Menlo, monospace',
              fontVariantNumeric: 'tabular-nums',
              color: '#7DD3FC',
              fontWeight: 600,
            }}
          >
            {formatMonth(labelMonth)}
          </span>
        </div>
      </div>

      {/* Chart panel */}
      <div
        style={{
          width: '100%',
          height: innerH,
          background: 'rgba(26,26,26,0.45)',
          borderRadius: 10,
          border: '1px solid rgba(255,255,255,0.05)',
          padding: 0,
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${innerW} ${innerH}`}
          preserveAspectRatio="none"
          style={{display: 'block'}}
        >
          <defs>
            {MODEL_KEYS.map((k) => (
              <linearGradient key={k} id={`mt-grad-${k}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={MODEL_COLORS[k].stroke} stopOpacity={0.6} />
                <stop offset="95%" stopColor={MODEL_COLORS[k].stroke} stopOpacity={0.05} />
              </linearGradient>
            ))}
          </defs>

          {/* Horizontal grid (dashed) */}
          {yTicks.map((v) => {
            const y = yFor(v);
            return (
              <line
                key={`grid-${v}`}
                x1={margin.left}
                x2={margin.left + plotW}
                y1={y}
                y2={y}
                stroke={CHART_COLORS.grid}
                strokeWidth={1}
                strokeDasharray="3 3"
              />
            );
          })}

          {/* Stacked area paths */}
          {stackedSeries.map(({key, topPoints, bottomPoints, stroke}) => {
            // Build a closed path: top edge (left -> right), then bottom edge (right -> left)
            const top = buildPolylinePath(topPoints);
            const bottomReversed = [...bottomPoints].reverse();
            const bottom = buildPolylinePath(bottomReversed)
              .replace(/^M /, 'L '); // continue from top
            const closed = `${top} ${bottom} Z`;
            return (
              <g key={key}>
                <path d={closed} fill={`url(#mt-grad-${key})`} stroke="none" />
                <path d={top} stroke={stroke} strokeWidth={1.5} fill="none" />
              </g>
            );
          })}

          {/* Y-axis tick labels */}
          {yTicks.map((v) => {
            const y = yFor(v);
            return (
              <text
                key={`yl-${v}`}
                x={margin.left - 6}
                y={y + 3}
                fill={CHART_COLORS.axisAndTicks}
                fontSize={9}
                textAnchor="end"
              >
                {v}%
              </text>
            );
          })}

          {/* X-axis tick labels */}
          {displayData.map((row, idx) => {
            if (!tickIdx.has(idx)) return null;
            const x = xFor(idx);
            return (
              <text
                key={`xl-${idx}`}
                x={x}
                y={margin.top + plotH + 14}
                fill={CHART_COLORS.axisAndTicks}
                fontSize={9}
                textAnchor="middle"
              >
                {formatMonth(row.month)}
              </text>
            );
          })}
        </svg>
      </div>

      {/* Legend (compact, single row of inline swatches for visible models) */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '4px 10px',
          marginTop: 8,
          fontSize: 10,
          color: 'rgba(255,255,255,0.7)',
        }}
      >
        {MODEL_KEYS.map((k) => {
          // only show legend entries that have appeared
          // A model has "appeared" once any revealed month (up to and
          // including the interpolated head) has a non-zero share.
          const headIdx = monthIdxHigh;
          const appeared =
            (interpolatedHead[k] || 0) > 0 ||
            normalized.slice(0, headIdx + 1).some((row) => (row[k] || 0) > 0);
          if (!appeared) return null;
          return (
            <span key={k} style={{display: 'inline-flex', alignItems: 'center', gap: 4}}>
              <span
                style={{
                  display: 'inline-block',
                  width: 8,
                  height: 8,
                  borderRadius: 2,
                  background: MODEL_COLORS[k].stroke,
                }}
              />
              {MODEL_COLORS[k].name}
            </span>
          );
        })}
      </div>

      {/* Cumulative-messages counter */}
      <div
        style={{
          marginTop: 'auto',
          paddingTop: 12,
          borderTop: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        <span
          style={{
            fontSize: 10,
            letterSpacing: '0.22em',
            textTransform: 'uppercase',
            color: 'rgba(255,255,255,0.45)',
          }}
        >
          Cumulative messages
        </span>
        <span
          style={{
            fontSize: 28,
            fontWeight: 700,
            color: '#fff',
            fontVariantNumeric: 'tabular-nums',
            fontFamily: 'ui-monospace, "SF Mono", Menlo, monospace',
            letterSpacing: '-0.01em',
          }}
        >
          {Math.round(cumulativeNow).toLocaleString('en-US')} messages
        </span>
      </div>
    </div>
  );
}
