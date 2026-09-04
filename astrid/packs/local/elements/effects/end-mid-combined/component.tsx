import type {ReactElement} from 'react';
import {
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {
  type ElementComponentProps,
  narrowParams,
} from '../../../../rendering/elements/_shared/contracts';

// Combined codex+minimax insert: one plate, one persistent timeline row,
// captions drawn per beat. References plug in (codex beat), then two images
// lift out with loading videos (minimax beat). No internal boundary.
type Params = {
  __astridAssets?: Record<string, string>;
};

const AMBER = '#ffa02e';
const ROW = ['card0', 'card1', 'card2', 'card3', 'card4'];
const REFS = ['card5', 'card6', 'card7'];
const PULLED = [1, 3];
const SPLIT = 0.44;

const CAPTION_1 =
  'I used Codex image generation to lock in the pixel style and keep our mink mascot consistent in every shot.';
const CAPTION_2 =
  'Then I animated it end to end in Minimax, trying masking workflows until the motion flowed, with smooth continuations between shots.';

const rowX = (i: number): number => -440 + i * 220;
const ROW_Y = 120;

const captionStyle = (show: number): Record<string, string | number> => ({
  position: 'absolute',
  left: '50%',
  top: -450,
  transform: 'translateX(-50%)',
  color: 'white',
  fontSize: 27,
  fontFamily: 'monospace',
  backgroundColor: 'rgba(0,0,0,0.6)',
  padding: '14px 26px',
  opacity: show,
  textAlign: 'center',
  width: 1400,
  lineHeight: 1.5,
  whiteSpace: 'normal',
});

export default function EndMidCombined(
  props: ElementComponentProps,
): ReactElement | null {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const params = narrowParams<Params>(props.params);
  const staged = params.__astridAssets ?? {};
  const url = (key: string): string => {
    const p = staged[key];
    return p ? staticFile(p) : staticFile(`astrid-effects/end-mid-combined/${key}`);
  };

  const D = Math.max(1, durationInFrames);
  const rowOn = interpolate(frame, [0, 0.06 * D], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const refOn = (i: number): number =>
    interpolate(frame, [(0.06 + (i / 3) * 0.1) * D, (0.06 + (i / 3) * 0.1 + 0.06) * D], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
  const beams = interpolate(frame, [0.16 * D, 0.28 * D], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const lift = interpolate(frame, [0.52 * D, 0.68 * D], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const loading = interpolate(frame, [0.68 * D, 0.86 * D], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const refFade = 1 - interpolate(frame, [0.4 * D, 0.5 * D], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const zoom = interpolate(frame, [0.92 * D, D], [1, 0.95], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const cap1 = 1 - interpolate(frame, [(SPLIT - 0.03) * D, SPLIT * D], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const cap2 = interpolate(frame, [(SPLIT - 0.03) * D, SPLIT * D], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const dots = loading >= 1 ? 3 : Math.floor(frame / (0.06 * D)) % 4;
  const trackOn = interpolate(frame, [0.02 * D, 0.1 * D], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden'}}>
      <Img
        src={url('base')}
        style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}}
      />
      <div
        style={{
          position: 'absolute',
          left: 960,
          top: 540,
          transform: `translate(-50%, -50%) scale(${zoom})`,
        }}
      >
        <div style={captionStyle(cap1)}>{CAPTION_1}</div>
        <div style={captionStyle(cap2)}>{CAPTION_2}</div>
        <div
          style={{
            position: 'absolute',
            left: -410,
            top: -320,
            width: 820,
            height: 200,
            border: '3px solid #3a2408',
            opacity: refOn(0) * refFade,
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
              opacity: refOn(0) * refFade,
            }}
          >
            REFERENCE IMAGES
          </div>
        </div>
        {REFS.map((key, i) => {
          const on = refOn(i);
          if (on <= 0) return null;
          const x = -260 + i * 260;
          return (
            <div key={key}>
              <Img
                src={url(key)}
                style={{
                  position: 'absolute',
                  left: x - 110,
                  top: -280,
                  width: 220 * on,
                  height: 124 * on,
                  border: '2px solid #3a2408',
                  opacity: on * refFade,
                }}
              />
              <div
                style={{
                  position: 'absolute',
                  left: x - 2,
                  top: -150,
                  width: 4,
                  height: 250 * beams,
                  backgroundColor: AMBER,
                  boxShadow: `0 0 16px ${AMBER}`,
                  opacity: beams * refFade,
                }}
              />
            </div>
          );
        })}
        <div
          style={{
            position: 'absolute',
            left: -560,
            top: ROW_Y + 120,
            width: 1120 * trackOn,
            height: 5,
            backgroundColor: AMBER,
            boxShadow: `0 0 20px ${AMBER}`,
            opacity: trackOn,
          }}
        />
        {ROW.map((key, i) => {
          const pulled = PULLED.includes(i);
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
                  opacity: rowOn,
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
                  boxShadow: `0 0 24px ${AMBER}`,
                  opacity: beams * rowOn,
                }}
              />
              {pulled && lift > 0 && (
                <div>
                  <div
                    style={{
                      position: 'absolute',
                      left: rowX(i) - 1,
                      top: ROW_Y + 101,
                      width: 3,
                      height: 120 * lift,
                      backgroundColor: AMBER,
                      boxShadow: `0 0 12px ${AMBER}`,
                    }}
                  />
                  <Img
                    src={url(key)}
                    style={{
                      position: 'absolute',
                      left: rowX(i) - 110,
                      top: ROW_Y + 101 + 120 * lift,
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
                      top: ROW_Y - 270,
                      width: 260,
                      height: 146,
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
                      top: ROW_Y - 124,
                      width: 3,
                      height: 124,
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
    </div>
  );
}
