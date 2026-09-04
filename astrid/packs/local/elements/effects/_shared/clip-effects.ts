import type {CSSProperties} from 'react';
import {Easing, interpolate} from 'remotion';

export type Anchor =
  | 'top-left' | 'top' | 'top-right'
  | 'left' | 'center' | 'right'
  | 'bottom-left' | 'bottom' | 'bottom-right';

export type Effects = {
  fade_in?: number;
  fade_out?: number;
  slide_in?: number;
  slide_out?: number;
  slide_in_x?: number;
  slide_out_x?: number;
};

const EFFECT_KEYS = ['fade_in', 'fade_out', 'slide_in', 'slide_out', 'slide_in_x', 'slide_out_x'] as const;

const pickEffectFields = (raw: unknown): Effects => {
  if (!raw || typeof raw !== 'object') return {};
  const out: Effects = {};
  for (const key of EFFECT_KEYS) {
    const v = (raw as Record<string, unknown>)[key];
    if (typeof v === 'number') out[key] = v;
  }
  return out;
};

export const normalizeEffects = (effects: unknown): Effects => {
  if (!effects) return {};
  if (Array.isArray(effects)) {
    return effects.reduce<Effects>(
      (acc, e) => ({...acc, ...pickEffectFields(e)}),
      {},
    );
  }
  return pickEffectFields(effects);
};

export const fadeOpacity = (
  effects: Effects,
  frame: number,
  durationInFrames: number,
  fps: number,
): number => {
  let opacity = 1;
  if (typeof effects.fade_in === 'number' && effects.fade_in > 0) {
    const f = Math.round(effects.fade_in * fps);
    opacity *= interpolate(frame, [0, f], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
  }
  if (typeof effects.fade_out === 'number' && effects.fade_out > 0) {
    const f = Math.round(effects.fade_out * fps);
    opacity *= interpolate(
      frame,
      [durationInFrames - f, durationInFrames],
      [1, 0],
      {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
    );
  }
  return opacity;
};

export const slideTransform = (
  effects: Effects,
  frame: number,
  durationInFrames: number,
  fps: number,
): string | undefined => {
  let translateX = 0;
  let translateY = 0;
  if (typeof effects.slide_in_x === 'number' && effects.slide_in_x !== 0 && (effects.fade_in ?? 0) > 0) {
    const f = Math.round((effects.fade_in ?? 0) * fps);
    translateX += interpolate(frame, [0, f], [effects.slide_in_x, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.out(Easing.cubic),
    });
  }
  if (typeof effects.slide_out_x === 'number' && effects.slide_out_x !== 0 && (effects.fade_out ?? 0) > 0) {
    const f = Math.round((effects.fade_out ?? 0) * fps);
    translateX += interpolate(
      frame,
      [durationInFrames - f, durationInFrames],
      [0, effects.slide_out_x],
      {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.in(Easing.cubic),
      },
    );
  }
  if (typeof effects.slide_in === 'number' && effects.slide_in !== 0 && (effects.fade_in ?? 0) > 0) {
    const f = Math.round((effects.fade_in ?? 0) * fps);
    translateY += interpolate(frame, [0, f], [effects.slide_in, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.out(Easing.cubic),
    });
  }
  if (typeof effects.slide_out === 'number' && effects.slide_out !== 0 && (effects.fade_out ?? 0) > 0) {
    const f = Math.round((effects.fade_out ?? 0) * fps);
    translateY += interpolate(
      frame,
      [durationInFrames - f, durationInFrames],
      [0, -effects.slide_out],
      {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.in(Easing.cubic),
      },
    );
  }
  if (translateX === 0 && translateY === 0) return undefined;
  return `translate(${translateX.toFixed(2)}px, ${translateY.toFixed(2)}px)`;
};

export const anchorPosition = (
  anchor: Anchor,
  offsetX: number,
  offsetY: number,
): CSSProperties => {
  // For center anchors we need translate(-50%) to actually center the
  // element — top:50%/left:50% only places the top-left corner there.
  const style: CSSProperties = {position: 'absolute'};
  let translateY = 0;
  let translateX = 0;
  if (anchor.startsWith('top')) {
    style.top = offsetY;
  } else if (anchor.startsWith('bottom')) {
    style.bottom = offsetY;
  } else {
    style.top = '50%';
    translateY = -50;
  }
  if (anchor.endsWith('left')) {
    style.left = offsetX;
  } else if (anchor.endsWith('right')) {
    style.right = offsetX;
  } else {
    style.left = '50%';
    translateX = -50;
  }
  if (translateX !== 0 || translateY !== 0) {
    style.transform = `translate(${translateX}%, ${translateY}%)`;
  }
  return style;
};
