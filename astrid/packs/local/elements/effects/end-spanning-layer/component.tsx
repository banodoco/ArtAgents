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

type Params = {
  __astridAssets?: Record<string, string>;
  deepSeekSeconds?: number;
  codexSeconds?: number;
  minimaxSeconds?: number;
  musicSeconds?: number;
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
] as const;
const DEEPSEEK_ORDER = [3, 0, 5, 1, 6, 2, 7, 4] as const;
const CODEX_ORDER = [4, 5, 6, 7, 0, 1, 2, 3] as const;
const DEFAULT_BEATS = [9.193, 6.383, 8.081, 6.124] as const;
const ROW_LEFT = -805;
const ROW_STEP = 230;
const CARD_WIDTH = 200;
const CARD_HEIGHT = (CARD_WIDTH / 420) * 236;

const clamp = (value: number): number => Math.max(0, Math.min(1, value));

const phase = (value: number, start: number, end: number): number =>
  interpolate(value, [start, end], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

const positiveSeconds = (value: number | undefined, fallback: number): number =>
  typeof value === 'number' && Number.isFinite(value) && value > 0
    ? value
    : fallback;

const rowX = (slot: number): number => ROW_LEFT + slot * ROW_STEP;

const gridOf = (index: number): {x: number; y: number} => ({
  x: -450 + (index % 4) * 300,
  y: -110 + Math.floor(index / 4) * 220,
});

type PreviewPanelProps = {
  image: string;
  left: number;
  top: number;
  width: number;
  height: number;
  opacity: number;
  progress: number;
  label: string;
};

function PreviewPanel({
  image,
  left,
  top,
  width,
  height,
  opacity,
  progress,
  label,
}: PreviewPanelProps): ReactElement {
  return (
    <div
      style={{
        position: 'absolute',
        left,
        top,
        width,
        height,
        overflow: 'hidden',
        backgroundColor: '#0b0703',
        border: `3px solid ${AMBER}`,
        boxShadow: `0 0 30px rgba(255,160,46,${0.25 + opacity * 0.35})`,
        opacity,
      }}
    >
      <Img
        src={image}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          opacity: 0.72,
        }}
      />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'linear-gradient(180deg, transparent 42%, rgba(8,5,2,0.88) 100%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: 14,
          bottom: 16,
          color: '#ffd6a3',
          fontFamily: 'monospace',
          fontSize: Math.max(13, Math.round(width / 18)),
          letterSpacing: 3,
        }}
      >
        {label}
      </div>
      <div
        style={{
          position: 'absolute',
          left: 12,
          right: 12,
          bottom: 8,
          height: 3,
          backgroundColor: 'rgba(255,255,255,0.18)',
        }}
      >
        <div
          style={{
            width: `${Math.round(progress * 100)}%`,
            height: '100%',
            backgroundColor: AMBER,
            boxShadow: `0 0 9px ${AMBER}`,
          }}
        />
      </div>
    </div>
  );
}

export default function EndSpanningLayer(
  props: ElementComponentProps,
): ReactElement | null {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const params = narrowParams<Params>(props.params);
  const staged = params.__astridAssets ?? {};
  const url = (key: string): string => {
    const asset = staged[key];
    return asset
      ? staticFile(asset)
      : staticFile(`astrid-effects/end-spanning-layer/${key}`);
  };

  const beats = [
    positiveSeconds(params.deepSeekSeconds, DEFAULT_BEATS[0]),
    positiveSeconds(params.codexSeconds, DEFAULT_BEATS[1]),
    positiveSeconds(params.minimaxSeconds, DEFAULT_BEATS[2]),
    positiveSeconds(params.musicSeconds, DEFAULT_BEATS[3]),
  ] as const;
  const totalSeconds = beats.reduce((sum, seconds) => sum + seconds, 0);
  const authoredSeconds =
    (frame / Math.max(1, durationInFrames)) * totalSeconds;
  const deepEnd = beats[0];
  const codexEnd = deepEnd + beats[1];
  const minimaxEnd = codexEnd + beats[2];
  const deepP = clamp(authoredSeconds / beats[0]);
  const codexP = clamp((authoredSeconds - deepEnd) / beats[1]);
  const minimaxP = clamp((authoredSeconds - codexEnd) / beats[2]);
  const musicP = clamp((authoredSeconds - minimaxEnd) / beats[3]);
  const inDeepSeek = authoredSeconds < deepEnd;
  const inCodex = authoredSeconds >= deepEnd && authoredSeconds < codexEnd;
  const inMinimax =
    authoredSeconds >= codexEnd && authoredSeconds < minimaxEnd;
  const inMusic = authoredSeconds >= minimaxEnd;

  // The row is the visual anchor. Each beat moves it just enough for the
  // complete row-plus-content group (rather than the row alone) to stay
  // vertically centered.
  const codexRowY =
    interpolate(codexP, [0, 0.2, 0.78, 1], [0, 135, 135, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    }) || 0;
  const minimaxRowY = interpolate(
    minimaxP,
    [0, 0.16, 0.82, 1],
    [0, 205, 205, 90],
    {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    },
  );
  const rowY = inDeepSeek
    ? 0
    : inCodex
      ? codexRowY
      : inMinimax
        ? minimaxRowY
        : 90;
  const trackOpacity = inDeepSeek ? phase(deepP, 0.45, 0.55) : 1;
  const trackWidth = 1760 * trackOpacity;
  const finalFade = inMusic ? 1 - phase(musicP, 0.84, 1) : 1;

  // Ending-carousel's original shuffle -> grid -> timeline -> reorder.
  const toLine = phase(deepP, 0.45, 0.7);
  const reorder = phase(deepP, 0.7, 0.92);
  const place = phase(deepP, 0.2, 0.3);
  const shuffleIndex = Math.min(5, Math.floor(deepP / (0.2 / 6)));
  const shuffleSize = interpolate(place, [0, 1], [620, 280]);
  const shuffleGrid = gridOf(0);
  const shuffleX = interpolate(place, [0, 1], [0, shuffleGrid.x]);
  const shuffleY = interpolate(place, [0, 1], [0, shuffleGrid.y]);

  // Codex: references arrive as the row settles downward, and every slot
  // crossfades in place so the persistent timeline geometry never jumps.
  const referencesOn = inCodex
    ? Math.min(phase(codexP, 0.04, 0.2), 1 - phase(codexP, 0.78, 0.96))
    : 0;
  const beamOn = phase(codexP, 0.14, 0.32) * referencesOn;

  // Minimax: two inputs at left feed a larger output at right while the
  // uninterrupted timeline remains below the panels.
  const panelsOn = inMinimax
    ? Math.min(phase(minimaxP, 0.04, 0.18), 1 - phase(minimaxP, 0.84, 0.98))
    : 0;
  const feedProgress = phase(minimaxP, 0.2, 0.72);
  const previewProgress = clamp(
    (Math.sin(frame * 0.055) * 0.08 + minimaxP * 0.92) * feedProgress,
  );

  // Music: a deterministic equalizer, waveform baseline, and playhead.
  const musicOn = inMusic ? phase(musicP, 0.03, 0.18) : 0;
  const equalizerBars = Array.from({length: 44}, (_, index) => {
    const envelope = 0.35 + 0.65 * Math.sin(((index + 1) / 45) * Math.PI);
    const pulse =
      0.48 +
      0.28 * Math.sin(frame * 0.22 + index * 0.73) +
      0.18 * Math.sin(frame * 0.09 - index * 0.41);
    return Math.max(8, 94 * envelope * clamp(pulse));
  });

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        overflow: 'hidden',
        opacity: finalFade,
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: 960,
          top: 540,
          transform: 'translate(-50%, -50%)',
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: -880,
            top: rowY + 82,
            width: trackWidth,
            height: 6,
            backgroundColor: AMBER,
            boxShadow: `0 0 24px ${AMBER}`,
            opacity: trackOpacity,
          }}
        />

        {inDeepSeek && deepP < 0.3 && (
          <Img
            src={url(CARD_KEYS[shuffleIndex])}
            style={{
              position: 'absolute',
              left: shuffleX - shuffleSize / 2,
              top: shuffleY - (shuffleSize / 420) * 118,
              width: shuffleSize,
              height: (shuffleSize / 420) * 236,
              border: place > 0 ? `5px solid ${AMBER}` : '2px solid #3a2408',
              boxShadow: place > 0 ? `0 0 50px ${AMBER}` : 'none',
            }}
          />
        )}

        {inDeepSeek &&
          CARD_KEYS.map((key, card) => {
            const enterStart =
              card === 0 ? 0.28 : 0.3 + ((card - 1) / 7) * 0.12;
            const enter = phase(deepP, enterStart, enterStart + 0.05);
            if (enter <= 0) return null;
            const grid = gridOf(card);
            const finalSlot = DEEPSEEK_ORDER.indexOf(
              card as (typeof DEEPSEEK_ORDER)[number],
            );
            const position = interpolate(
              reorder,
              [0, 1],
              [card, finalSlot],
            );
            const destinationX = rowX(position);
            const lift =
              Math.sin(Math.PI * toLine) * 90 +
              Math.sin(Math.PI * reorder) * 70;
            const x = interpolate(toLine, [0, 1], [grid.x, destinationX]);
            const y = interpolate(toLine, [0, 1], [grid.y, rowY]) - lift;
            const width = interpolate(toLine, [0, 1], [280, CARD_WIDTH]);
            const height = (width / 420) * 236;
            return (
              <Img
                key={key}
                src={url(key)}
                style={{
                  position: 'absolute',
                  left: x - (width * enter) / 2,
                  top: y - (height * enter) / 2,
                  width: Math.max(0.01, width * enter),
                  height: Math.max(0.01, height * enter),
                  border: '2px solid #3a2408',
                  opacity: enter,
                }}
              />
            );
          })}

        {!inDeepSeek &&
          DEEPSEEK_ORDER.map((oldCard, slot) => {
            const crossfade = inCodex
              ? phase(codexP, 0.28 + slot * 0.045, 0.48 + slot * 0.045)
              : authoredSeconds >= codexEnd
                ? 1
                : 0;
            const newCard = CODEX_ORDER[slot];
            const x = rowX(slot);
            const flash = Math.sin(Math.PI * crossfade);
            return (
              <div key={slot}>
                <div
                  style={{
                    position: 'absolute',
                    left: x - CARD_WIDTH / 2 - 7,
                    top: rowY - CARD_HEIGHT / 2 - 7,
                    width: CARD_WIDTH + 14,
                    height: CARD_HEIGHT + 14,
                    border: `2px solid ${AMBER}`,
                    boxShadow: `0 0 ${Math.round(34 * flash)}px ${AMBER}`,
                    opacity: 0.16 + flash * 0.7,
                  }}
                />
                <Img
                  src={url(CARD_KEYS[oldCard])}
                  style={{
                    position: 'absolute',
                    left: x - CARD_WIDTH / 2,
                    top: rowY - CARD_HEIGHT / 2,
                    width: CARD_WIDTH,
                    height: CARD_HEIGHT,
                    border: '2px solid #3a2408',
                    opacity: 1 - crossfade,
                  }}
                />
                <Img
                  src={url(CARD_KEYS[newCard])}
                  style={{
                    position: 'absolute',
                    left: x - CARD_WIDTH / 2,
                    top: rowY - CARD_HEIGHT / 2,
                    width: CARD_WIDTH,
                    height: CARD_HEIGHT,
                    border: '2px solid #3a2408',
                    opacity: crossfade,
                  }}
                />
              </div>
            );
          })}

        {inCodex && (
          <div style={{opacity: referencesOn}}>
            {[0, 1, 2].map((card, referenceIndex) => {
              const x = -310 + referenceIndex * 310;
              const targetSlot = CODEX_ORDER.indexOf(
                card as (typeof CODEX_ORDER)[number],
              );
              const targetX = rowX(targetSlot);
              const beamWidth = Math.abs(targetX - x);
              return (
                <div key={card}>
                  <Img
                    src={url(CARD_KEYS[card])}
                    style={{
                      position: 'absolute',
                      left: x - 125,
                      top: -245,
                      width: 250,
                      height: 140,
                      objectFit: 'cover',
                      border: `3px solid ${AMBER}`,
                      boxShadow: `0 0 24px rgba(255,160,46,0.45)`,
                    }}
                  />
                  <div
                    style={{
                      position: 'absolute',
                      left: Math.min(x, targetX),
                      top: -93,
                      width: beamWidth,
                      height: 3,
                      backgroundColor: AMBER,
                      boxShadow: `0 0 14px ${AMBER}`,
                      opacity: beamOn,
                      transform: `rotate(${
                        Math.atan2(rowY + 33, targetX - x) * (180 / Math.PI)
                      }deg)`,
                      transformOrigin: targetX >= x ? 'left center' : 'right center',
                    }}
                  />
                </div>
              );
            })}
            <div
              style={{
                position: 'absolute',
                left: -465,
                top: -286,
                width: 930,
                color: AMBER,
                fontFamily: 'monospace',
                fontSize: 22,
                letterSpacing: 7,
                textAlign: 'center',
              }}
            >
              REFERENCE INPUTS
            </div>
          </div>
        )}

        {inMinimax && (
          <div style={{opacity: panelsOn}}>
            <PreviewPanel
              image={url('card0')}
              left={-650}
              top={-255}
              width={300}
              height={150}
              opacity={panelsOn}
              progress={clamp(previewProgress * 1.12)}
              label="SOURCE A"
            />
            <PreviewPanel
              image={url('card2')}
              left={-650}
              top={-75}
              width={300}
              height={150}
              opacity={panelsOn}
              progress={clamp(previewProgress * 0.88)}
              label="SOURCE B"
            />
            <PreviewPanel
              image={url('card6')}
              left={80}
              top={-215}
              width={570}
              height={300}
              opacity={panelsOn}
              progress={previewProgress}
              label="GENERATED VIDEO"
            />
            {[-180, 0].map((sourceY, index) => (
              <div
                key={sourceY}
                style={{
                  position: 'absolute',
                  left: -338,
                  top: sourceY,
                  width: 430 * feedProgress,
                  height: 4,
                  backgroundColor: AMBER,
                  boxShadow: `0 0 18px ${AMBER}`,
                  opacity: panelsOn,
                  transform: `rotate(${index === 0 ? 12 : -12}deg)`,
                  transformOrigin: 'left center',
                }}
              />
            ))}
          </div>
        )}

        {inMusic && (
          <div style={{opacity: musicOn}}>
            <div
              style={{
                position: 'absolute',
                left: -650,
                top: -160,
                width: 1300,
                height: 126,
                borderTop: '1px solid rgba(255,160,46,0.3)',
                borderBottom: '1px solid rgba(255,160,46,0.3)',
              }}
            >
              {equalizerBars.map((height, index) => {
                const x = 8 + index * 29;
                const played = index / equalizerBars.length <= musicP;
                return (
                  <div
                    key={index}
                    style={{
                      position: 'absolute',
                      left: x,
                      top: 63 - height / 2,
                      width: 9,
                      height,
                      borderRadius: 5,
                      backgroundColor: played ? AMBER : '#573818',
                      boxShadow: played ? `0 0 11px ${AMBER}` : 'none',
                    }}
                  />
                );
              })}
              <div
                style={{
                  position: 'absolute',
                  left: 0,
                  top: 62,
                  width: '100%',
                  height: 2,
                  backgroundColor: 'rgba(255,214,163,0.42)',
                }}
              />
              <div
                style={{
                  position: 'absolute',
                  left: musicP * 1300 - 2,
                  top: -10,
                  width: 4,
                  height: 146,
                  backgroundColor: '#fff0db',
                  boxShadow: '0 0 18px #fff0db',
                }}
              />
            </div>
            <div
              style={{
                position: 'absolute',
                left: -650,
                top: -198,
                color: AMBER,
                fontFamily: 'monospace',
                fontSize: 20,
                letterSpacing: 7,
              }}
            >
              AUDIO TIMELINE
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
