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

// Minimax-animate insert (shot 17): a timeline row appears; two images lift
// out below, each connected to a video card above that loads then plays.
// Duration-relative phases; transparent-safe fx-track overlay.
type Params = {
  __astridAssets?: Record<string, string>;
};

const AMBER = '#ffa02e';
const ROW = ['card0', 'card1', 'card2', 'card3', 'card4'];
const PULLED = [1, 3];

const rowX = (i: number): number => -440 + i * 220;
const ROW_Y = -60;

export default function EndMinimaxAnimate(
  props: ElementComponentProps,
): ReactElement | null {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const params = narrowParams<Params>(props.params);
  const staged = params.__astridAssets ?? {};
  const url = (key: string): string => {
    const p = staged[key];
    return p ? staticFile(p) : staticFile(`astrid-effects/end-minimax-animate/${key}`);
  };

  const D = Math.max(1, durationInFrames);
  const rowOn = interpolate(frame, [0, 0.12 * D], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const lift = interpolate(frame, [0.15 * D, 0.38 * D], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const loading = interpolate(frame, [0.4 * D, 0.68 * D], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const zoom = interpolate(frame, [0.9 * D, D], [1, 0.95], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  // Loading dots: 0..2 cycle while loading < 1.
  const dots = loading >= 1 ? 3 : Math.floor(frame / (0.09 * D)) % 4;
  const pulse = loading >= 1 ? 1 + 0.03 * Math.sin((frame / D) * Math.PI * 6) : 1;

  // Push-up cover: shot 16's last frame slides up over the first 0.6s,
  // so the cut carries over instead of breaking.
  const coverY = interpolate(frame, [0, 18], [0, -1080], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const showCover = frame < 19;
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
          top: 500,
          transform: `translate(-50%, -50%) scale(${zoom})`,
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: -560,
            top: ROW_Y + 120,
            width: 1120 * rowOn,
            height: 5,
            backgroundColor: AMBER,
            boxShadow: `0 0 20px ${AMBER}`,
            opacity: rowOn,
          }}
        />
        {ROW.map((key, i) => {
          const pulled = PULLED.includes(i);
          const y = ROW_Y;
          return (
            <div key={key}>
              <Img
                src={url(key)}
                style={{
                  position: 'absolute',
                  left: rowX(i) - 90,
                  top: y,
                  width: 180,
                  height: 101,
                  border: '2px solid #3a2408',
                  opacity: rowOn,
                }}
              />
              {pulled && lift > 0 && (
                <div>
                  <div
                    style={{
                      position: 'absolute',
                      left: rowX(i) - 1,
                      top: y + 101,
                      width: 3,
                      height: 130 * lift,
                      backgroundColor: AMBER,
                      boxShadow: `0 0 12px ${AMBER}`,
                    }}
                  />
                  <Img
                    src={url(key)}
                    style={{
                      position: 'absolute',
                      left: rowX(i) - 110,
                      top: y + 101 + 130 * lift,
                      width: 220,
                      height: 124,
                      border: `3px solid ${AMBER}`,
                      boxShadow: `0 0 26px ${AMBER}`,
                      opacity: lift,
                    }}
                  />
                  <div
                    style={{
                      position: 'absolute',
                      left: rowX(i) - 130,
                      top: y - 250,
                      width: 260 * pulse,
                      height: 146 * pulse,
                      border: `3px solid ${AMBER}`,
                      boxShadow: `0 0 30px ${AMBER}`,
                      backgroundColor: '#0a0603',
                      opacity: lift,
                    }}
                  >
                    <Img
                      src={url(key)}
                      style={{
                        position: 'absolute',
                        inset: 0,
                        width: '100%',
                        height: '100%',
                        opacity: 0.85,
                      }}
                    />
                    <div
                      style={{
                        position: 'absolute',
                        left: '50%',
                        top: '50%',
                        transform: 'translate(-50%,-50%)',
                        width: 0,
                        height: 0,
                        borderLeft: '26px solid #ffb14e',
                        borderTop: '16px solid transparent',
                        borderBottom: '16px solid transparent',
                        opacity: loading >= 1 ? 1 : 0.35,
                      }}
                    />
                    {loading < 1 && (
                      <div
                        style={{
                          position: 'absolute',
                          left: 0,
                          right: 0,
                          bottom: 10,
                          textAlign: 'center',
                          color: '#ffb14e',
                          fontSize: 30,
                          fontFamily: 'monospace',
                        }}
                      >
                        {'●'.repeat(dots) + '○'.repeat(3 - dots)}
                      </div>
                    )}
                  </div>
                  <div
                    style={{
                      position: 'absolute',
                      left: rowX(i) - 1,
                      top: y - 104,
                      width: 3,
                      height: 104,
                      backgroundColor: AMBER,
                      boxShadow: `0 0 12px ${AMBER}`,
                      opacity: lift,
                    }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
      {showCover && (
        <Img
          src={url('cover16last')}
          style={{
            position: 'absolute',
            left: 0,
            top: coverY,
            width: 1920,
            height: 1080,
          }}
        />
      )}
    </div>
  );
}
