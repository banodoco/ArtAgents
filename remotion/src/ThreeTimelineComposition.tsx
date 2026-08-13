// ThreeTimelineComposition.tsx
//
// Remotion composition that renders an Astrid serialized timeline as a
// three.js scene. It consumes the SAME props shape as the existing
// `TimelineComposition` (see `Root.tsx`): `{timeline, assets, theme?}`.
//
// Rendering model
// ---------------
// * `<ThreeCanvas>` (from `@remotion/three`) drives rendering: during
//   Remotion renders it forces `frameloop="never"` and calls
//   `state.advance()` once per frame (ManualFrameRenderer), synced to
//   `useCurrentFrame()`. We do NOT use useFrame/requestAnimationFrame or
//   any wall-clock source — every frame the React render derives the scene
//   purely from `frame / fps` and the serialized timeline.
// * ORTHOGRAPHIC camera in pixel space: world units map 1:1 to output
//   pixels. R3F normalizes the ortho frustum to
//   [-width/2, width/2] x [height/2, -height/2] (origin-centered, y up)
//   whenever the canvas size changes, so a pixel (px, py) measured from
//   the top-left corner lives at world (px - width/2, height/2 - py).
//   The camera sits at z=+10 looking at the z=0 plane (declarative camera
//   with default rotation faces -z).
// * Each visible text clip is drawn into an offscreen 2D canvas
//   (document.createElement('canvas'), same pixel size as the output),
//   uploaded as a THREE.CanvasTexture on a full-canvas PlaneGeometry
//   centered at world (0, 0, z). The default flipY=true maps the canvas
//   top row to the plane's +y edge (screen top), so canvas pixels land at
//   their exact output coordinates.
// * Scene background is a plain `<color attach="background">` so it shows
//   even with zero clips.
//
// Z ordering
// ----------
// Astrid visual tracks paint in reversed array order (later track = on
// top). The camera is at positive z looking at the z=0 plane, so "nearer
// the camera" == larger z. We iterate visual tracks in reversed paint
// order and assign z = -paintIndex: the first-painted (bottom) track gets
// the most negative z (farthest), the top track gets z=0 (nearest).
// `mesh.renderOrder = trackIndex` additionally forces draw order for the
// transparent planes, independent of three.js' internal transparent sort.
//
// Field mapping (exact set, everything else ignored)
// --------------------------------------------------
// text.content | text.fontSize | text.color | text.align | text.bold
// params.anchor | params.offsetX | params.offsetY | params.textShadow
// params.maxWidth | params.weight
//
// Fonts are a fixed generic sans-serif stack (no network fonts). No
// lights/shaders/post-processing/Drei; materials are MeshBasicMaterial
// (unlit, texture-only).

import {useEffect, useMemo} from 'react';
import type {ReactElement} from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import * as THREE from 'three';
import type {TimelineCompositionProps} from '@banodoco/timeline-composition';
import type {
  TimelineThemeOverrides,
  VisualOverrides,
} from './types.augmentations';

const DEFAULT_BACKGROUND = '#000000';
const DEFAULT_FONT_SIZE = 48;
const DEFAULT_TEXT_COLOR = '#ffffff';
const DEFAULT_ALIGN: CanvasTextAlign = 'center';
const DEFAULT_HOLD_SECONDS = 1;
const FONT_FAMILY = '"Helvetica Neue", Helvetica, Arial, sans-serif';
const LINE_HEIGHT_MULTIPLIER = 1.2;

const CAMERA_Z = 10;
const CAMERA_NEAR = 1;
const CAMERA_FAR = 2000;

type TextPlaneData = {
  clipId: string;
  mesh: THREE.Mesh;
  texture: THREE.CanvasTexture;
  geometry: THREE.PlaneGeometry;
  material: THREE.MeshBasicMaterial;
};

type ParsedShadow = {
  offsetX: number;
  offsetY: number;
  blur: number;
  color: string;
};

// Minimal structural views of the serialized timeline (the package's own
// `TimelineClip`/`TrackDefinition` types are not re-exported from its
// index; the props shape is the JSON contract from Root.tsx).
type SerializedClip = {
  id?: string;
  at?: number;
  track?: string;
  clipType?: string;
  hold?: number;
  text?: unknown;
  params?: Record<string, unknown>;
};

type SerializedTrack = {
  id?: string;
  kind?: string;
};

const getString = (value: unknown): string | null => {
  return typeof value === 'string' ? value : null;
};

const getNumber = (value: unknown): number | null => {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
};

const getPositiveNumber = (value: unknown): number | null => {
  const n = getNumber(value);
  return n !== null && n > 0 ? n : null;
};

// Background priority: theme_overrides.visual.background →
// merged theme visual.color.bg → black. Never null so the scene always
// has a resolved background, even with no clips.
const resolveBackground = (props: TimelineCompositionProps): string => {
  const overrides = props.timeline.theme_overrides as
    | TimelineThemeOverrides
    | undefined;
  const visual = overrides?.visual as VisualOverrides | undefined;
  const overrideBackground = visual?.background;
  if (
    typeof overrideBackground === 'string' &&
    overrideBackground.trim() !== ''
  ) {
    return overrideBackground;
  }
  const themeBackground = props.theme?.visual?.color?.bg;
  if (typeof themeBackground === 'string' && themeBackground.trim() !== '') {
    return themeBackground;
  }
  return DEFAULT_BACKGROUND;
};

// CSS `text-shadow` is "offsetX offsetY blur color" (color may contain
// spaces, e.g. "rgba(0, 0, 0, 0.75)"); 3-part form omits blur. Mirrors the
// passthrough of the established hyperframes mapping.
const parseTextShadow = (shadow: string | null): ParsedShadow | null => {
  if (!shadow) {
    return null;
  }
  const parts = shadow.trim().split(/\s+/);
  if (parts.length < 3) {
    return null;
  }
  const toNumber = (part: string): number => {
    const n = Number.parseFloat(part);
    return Number.isFinite(n) ? n : 0;
  };
  if (parts.length >= 4) {
    return {
      offsetX: toNumber(parts[0]),
      offsetY: toNumber(parts[1]),
      blur: toNumber(parts[2]),
      color: parts.slice(3).join(' '),
    };
  }
  return {
    offsetX: toNumber(parts[0]),
    offsetY: toNumber(parts[1]),
    blur: 0,
    color: parts[2],
  };
};

// Word-wrap into lines that fit `maxWidth` (0 / negative = single line).
const wrapText = (
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
): string[] => {
  if (maxWidth <= 0) {
    return [text];
  }
  const lines: string[] = [];
  let current = '';
  for (const word of text.split(/\s+/)) {
    if (!word) {
      continue;
    }
    const candidate = current ? `${current} ${word}` : word;
    if (!current || ctx.measureText(candidate).width <= maxWidth) {
      current = candidate;
    } else {
      lines.push(current);
      current = word;
    }
  }
  if (current) {
    lines.push(current);
  }
  return lines.length > 0 ? lines : [''];
};

// Draw the clip's text into an offscreen 2D canvas of the output size and
// return it. Returns null when the clip carries no usable text.
const drawTextCanvas = (
  clip: SerializedClip,
  width: number,
  height: number,
): HTMLCanvasElement | null => {
  const textField =
    typeof clip.text === 'object' && clip.text !== null
      ? (clip.text as Record<string, unknown>)
      : {};
  const params = clip.params ?? {};

  const content = getString(textField.content);
  if (content === null || content.length === 0) {
    return null;
  }

  const fontSize = getPositiveNumber(textField.fontSize) ?? DEFAULT_FONT_SIZE;
  const color = getString(textField.color) ?? DEFAULT_TEXT_COLOR;
  const align = getString(textField.align);
  const textAlign: CanvasTextAlign =
    align === 'left' || align === 'center' || align === 'right'
      ? align
      : DEFAULT_ALIGN;
  const bold = textField.bold === true;
  const weightParam = getNumber(params.weight);
  const weight = weightParam !== null ? Math.round(weightParam) : bold ? 700 : 400;
  const anchor = (getString(params.anchor) ?? '').toLowerCase();
  const offsetX = getNumber(params.offsetX) ?? 0;
  const offsetY = getNumber(params.offsetY) ?? 0;
  const maxWidth = getPositiveNumber(params.maxWidth) ?? 0;
  const shadow = parseTextShadow(getString(params.textShadow));

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    return canvas;
  }

  ctx.font = `${weight} ${fontSize}px ${FONT_FAMILY}`;
  const lines = wrapText(ctx, content, maxWidth);
  const lineHeight = fontSize * LINE_HEIGHT_MULTIPLIER;
  const blockHeight = lines.length * lineHeight;

  // anchor: compound string of an optional vertical (top/middle/bottom)
  // and horizontal (left/center/right) component; it picks the reference
  // point of the text block, then offsetX/offsetY shift away from it
  // (default anchor = center, matching the flex-centered hyperframes
  // layout where offsets push right/down). `align` sets the text
  // alignment at that reference point.
  const hAnchor = anchor.includes('left')
    ? 'left'
    : anchor.includes('right')
      ? 'right'
      : 'center';
  const vAnchor = anchor.includes('top')
    ? 'top'
    : anchor.includes('bottom')
      ? 'bottom'
      : 'center';

  let x: number;
  if (hAnchor === 'left') {
    x = offsetX;
  } else if (hAnchor === 'right') {
    x = width - offsetX;
  } else {
    x = width / 2 + offsetX;
  }
  let yTop: number;
  if (vAnchor === 'top') {
    yTop = offsetY;
  } else if (vAnchor === 'bottom') {
    yTop = height - offsetY - blockHeight;
  } else {
    yTop = height / 2 + offsetY - blockHeight / 2;
  }

  ctx.textAlign = textAlign;
  ctx.textBaseline = 'top';
  ctx.fillStyle = color;
  if (shadow) {
    ctx.shadowColor = shadow.color;
    ctx.shadowBlur = shadow.blur;
    ctx.shadowOffsetX = shadow.offsetX;
    ctx.shadowOffsetY = shadow.offsetY;
  }
  for (let i = 0; i < lines.length; i++) {
    ctx.fillText(lines[i], x, yTop + i * lineHeight);
  }
  return canvas;
};

const isTextClip = (clip: SerializedClip): boolean => {
  return clip.clipType === 'text';
};

// Serialized view of the visual tracks (id + paint order in `tracks`).
const getVisualTracks = (props: TimelineCompositionProps): SerializedTrack[] => {
  const tracks = Array.isArray(props.timeline.tracks)
    ? props.timeline.tracks
    : [];
  return tracks.filter((track) => track.kind === 'visual') as SerializedTrack[];
};

// Deterministic per-frame scene: one full-canvas plane per text clip
// visible at `frame/fps` (visible iff frame/fps in [at, at+hold)).
const buildTextPlanes = (
  props: TimelineCompositionProps,
  frame: number,
  fps: number,
  width: number,
  height: number,
): TextPlaneData[] => {
  const timeline = props.timeline;
  const visualTracks = getVisualTracks(props);
  const time = frame / fps;

  const planes: TextPlaneData[] = [];
  for (const clip of timeline.clips ?? []) {
    if (!isTextClip(clip)) {
      continue;
    }
    const at =
      typeof clip.at === 'number' && Number.isFinite(clip.at) ? clip.at : 0;
    const hold =
      typeof clip.hold === 'number' &&
      Number.isFinite(clip.hold) &&
      clip.hold > 0
        ? clip.hold
        : DEFAULT_HOLD_SECONDS;
    if (time < at || time >= at + hold) {
      continue;
    }
    const trackIndex = visualTracks.findIndex((track) => track.id === clip.track);
    if (trackIndex === -1) {
      continue;
    }
    const canvas = drawTextCanvas(clip, width, height);
    if (!canvas) {
      continue;
    }

    const texture = new THREE.CanvasTexture(canvas);
    // Default flipY=true maps the canvas top row to the plane's +y edge,
    // which is the screen top in the y-up frustum — pixel-exact.
    texture.colorSpace = THREE.SRGBColorSpace;
    const geometry = new THREE.PlaneGeometry(width, height);
    const material = new THREE.MeshBasicMaterial({
      map: texture,
      transparent: true,
      depthWrite: false,
    });
    const mesh = new THREE.Mesh(geometry, material);

    // Reversed paint order: last visual track on top (nearest camera).
    // The full-canvas plane is centered at the frustum origin (0, 0).
    const paintIndex = visualTracks.length - 1 - trackIndex;
    mesh.position.set(0, 0, -paintIndex);
    mesh.renderOrder = trackIndex;
    planes.push({clipId: clip.id, mesh, texture, geometry, material});
  }
  return planes;
};

// Renders one imperative plane. Disposes texture, geometry and material
// whenever the data is replaced (per frame) and on unmount.
const TextPlane = ({data}: {data: TextPlaneData}): ReactElement => {
  useEffect(() => {
    return () => {
      data.texture.dispose();
      data.geometry.dispose();
      data.material.dispose();
    };
  }, [data]);
  return <primitive object={data.mesh} />;
};

export const ThreeTimelineComposition = (
  props: TimelineCompositionProps,
): ReactElement => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const background = useMemo(() => resolveBackground(props), [props]);
  const planes = useMemo(
    () => buildTextPlanes(props, frame, fps, width, height),
    [props, frame, fps, width, height],
  );

  return (
    <ThreeCanvas
      width={width}
      height={height}
      orthographic
      camera={{
        left: -width / 2,
        right: width / 2,
        top: height / 2,
        bottom: -height / 2,
        near: CAMERA_NEAR,
        far: CAMERA_FAR,
        position: [0, 0, CAMERA_Z],
      }}
    >
      <color attach="background" args={[background]} />
      {planes.map((data) => (
        <TextPlane key={data.clipId} data={data} />
      ))}
    </ThreeCanvas>
  );
};
