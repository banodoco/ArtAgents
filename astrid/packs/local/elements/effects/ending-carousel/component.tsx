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

// Ending-carousel insert for the Astrid intro (shot 15). Base plate
// full-screen, then over the middle band: shuffle (one big card cycling
// fast), highlight + place (winner glows and flies to grid slot 0),
// grid fill (rest pop in), timeline (all fly onto an amber track),
// reorder (swap into final order with a lift). Duration-relative.
type Params = {
  __astridAssets?: Record<string, string>;
};

const AMBER = '#ffa02e';

const CARD_KEYS = [
  'card0',
  'card1',
  'card2',
  'card3',
  'card4',
  'card5',
  'card6',
  'card7',
];

const FINAL_ORDER = [3, 0, 5, 1, 6, 2, 7, 4];
const SHUFFLE_LAST = 5;

const gridOf = (i: number): {x: number; y: number} => ({
  x: -450 + (i % 4) * 300,
  y: -110 + Math.floor(i / 4) * 220,
});

export default function EndingCarousel(
  props: ElementComponentProps,
): ReactElement | null {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const params = narrowParams<Params>(props.params);
  const staged = params.__astridAssets ?? {};
  const url = (key: string): string => {
    const p = staged[key];
    return p ? staticFile(p) : staticFile(`astrid-effects/ending-carousel/${key}`);
  };
  const D = Math.max(1, durationInFrames);
  const toLine = interpolate(frame, [0.45 * D, 0.7 * D], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const reorder = interpolate(frame, [0.7 * D, 0.92 * D], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const zoom = interpolate(frame, [0.92 * D, D], [1, 0.94], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const trackOn = interpolate(frame, [0.45 * D, 0.55 * D], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const orderPosOf = (i: number): number => {
    const to = FINAL_ORDER.indexOf(i);
    return interpolate(reorder, [0, 1], [i, to]);
  };

  // Shuffle: cycle cards 0..5 big in the center, then the winner glows
  // and flies to grid slot 0.
  const showShuffle = frame < 0.3 * D;
  const shuffleIdx = Math.min(
    SHUFFLE_LAST,
    Math.floor(frame / ((0.2 * D) / 6)),
  );
  const place = interpolate(frame, [0.2 * D, 0.3 * D], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const g0 = gridOf(0);
  const shuffleW = 620;
  const shuffleX = interpolate(place, [0, 1], [0, g0.x]);
  const shuffleY = interpolate(place, [0, 1], [0, g0.y]);
  const shuffleSize = interpolate(place, [0, 1], [shuffleW, 280]);

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
          top: 560,
          transform: `translate(-50%, -50%) scale(${zoom})`,
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: -880,
            top: 150,
            width: 1760 * trackOn,
            height: 6,
            backgroundColor: AMBER,
            boxShadow: `0 0 24px ${AMBER}`,
            opacity: trackOn,
          }}
        />
        {showShuffle && (
          <Img
            src={url(CARD_KEYS[shuffleIdx])}
            style={{
              position: 'absolute',
              left: shuffleX - shuffleSize / 2,
              top: shuffleY - (shuffleSize / 420) * 236 / 2,
              height: (shuffleSize / 420) * 236,
              border: place > 0 ? `5px solid ${AMBER}` : '2px solid #3a2408',
              boxShadow: place > 0 ? `0 0 50px ${AMBER}` : 'none',
            }}
          />
        )}
        {CARD_KEYS.map((key, i) => {
          // Winner lands as grid slot 0; the rest pop in staggered.
          const t0 = i === 0 ? 0.28 * D : (0.3 + ((i - 1) / 7) * 0.12) * D;
          const enter = interpolate(frame, [t0, t0 + 0.05 * D], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          });
          if (enter <= 0) return null;
          const g = gridOf(i);
          const op = orderPosOf(i);
          const tx = -805 + op * 230;
          const ty = 150;
          const liftLine = Math.sin(Math.PI * toLine) * 90;
          const liftRe = Math.sin(Math.PI * reorder) * 70;
          const x = interpolate(toLine, [0, 1], [g.x, tx]);
          const y = interpolate(toLine, [0, 1], [g.y, ty]) - liftLine - liftRe;
          const w = interpolate(toLine, [0, 1], [280, 200]);
          const h = (w / 420) * 236;
          return (
            <Img
              key={key}
              src={url(key)}
              style={{
                position: 'absolute',
                left: x - (w * enter) / 2,
                top: y - (h * enter) / 2,
                width: w * enter,
                height: h * enter,
                border: '2px solid #3a2408',
                opacity: enter,
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
