import type {ReactElement} from 'react';
import {
  Img,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {
  type ElementComponentProps,
  narrowParams,
} from '../../../../rendering/elements/_shared/contracts';

// Codex-transform insert (shot 16): three reference cards above beam into
// a timeline row; targets flash, glow amber, and swap into new images.
// Duration-relative phases; transparent-safe fx-track overlay.
type Params = {
  __astridAssets?: Record<string, string>;
};

const AMBER = '#ffa02e';
const REFS = ['card0', 'card1', 'card2'];
const ROW = ['card3', 'card4', 'card5', 'card6'];
const SWAPPED = ['card4', 'card5', 'card6', 'card7'];
const TARGETS = [0, 1, 2, 3];

const rowX = (i: number): number => -330 + i * 220;
const ROW_Y = 120;

export default function EndCodexTransform(
  props: ElementComponentProps,
): ReactElement | null {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const params = narrowParams<Params>(props.params);
  const staged = params.__astridAssets ?? {};
  const url = (key: string): string => {
    const p = staged[key];
    return p ? staticFile(p) : staticFile(`astrid-effects/end-codex-transform/${key}`);
  };

  const D = Math.max(1, durationInFrames);
  const refsOn = (i: number): number =>
    interpolate(frame, [(i / 3) * 0.15 * D, ((i / 3) * 0.15 + 0.08) * D], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
  const beams = interpolate(frame, [0.2 * D, 0.35 * D], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const zoom = interpolate(frame, [0.88 * D, D], [1, 0.94], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden'}}>
      <OffthreadVideo
        src={url('plate')}
        muted
        style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}}
      />
      <div
        style={{
          position: 'absolute',
          left: 960,
          top: 520,
          transform: `translate(-50%, -50%) scale(${zoom})`,
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: -410,
            top: -260,
            width: 820,
            height: 200,
            border: '3px solid #3a2408',
            opacity: refsOn(0),
          }}
        >
          <div
            style={{
              position: 'absolute',
              left: 12,
              top: -34,
              color: AMBER,
              fontSize: 24,
              fontFamily: 'monospace',
              letterSpacing: 6,
              opacity: refsOn(0),
            }}
          >
            REFERENCE IMAGES
          </div>
        </div>
        {REFS.map((key, i) => {
          const on = refsOn(i);
          if (on <= 0) return null;
          const x = -260 + i * 260;
          return (
            <div key={key}>
              <Img
                src={url(key)}
                style={{
                  position: 'absolute',
                  left: x - 110,
                  top: -220,
                  width: 220 * on,
                  height: 124 * on,
                  border: '2px solid #3a2408',
                  opacity: on,
                }}
              />
              <div
                style={{
                  position: 'absolute',
                  left: x - 2,
                  top: -90,
                  width: 4,
                  height: 220 * beams,
                  backgroundColor: AMBER,
                  boxShadow: `0 0 16px ${AMBER}`,
                  opacity: beams,
                }}
              />
            </div>
          );
        })}
        <div
          style={{
            position: 'absolute',
            left: -450,
            top: ROW_Y + 130,
            width: 900,
            height: 5,
            backgroundColor: AMBER,
            boxShadow: `0 0 20px ${AMBER}`,
            opacity: beams,
          }}
        />
        {ROW.map((key, i) => {
          const plugged = [-260, 0, 260].some((bx) => Math.abs(rowX(i) - bx) < 120)
            ? beams
            : 0;
          return (
            <div key={key}>
              <Img
                src={url(key)}
                style={{
                  position: 'absolute',
                  left: rowX(i) - 90,
                  top: ROW_Y,
                  width: 180,
                  height: 101,
                  border: '2px solid #3a2408',
                }}
              />
              <div
                style={{
                  position: 'absolute',
                  left: rowX(i) - 8,
                  top: ROW_Y - 12,
                  width: 16,
                  height: 16,
                  borderRadius: 8,
                  backgroundColor: AMBER,
                  boxShadow: `0 0 ${8 + 20 * plugged}px ${AMBER}`,
                  opacity: plugged,
                }}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
