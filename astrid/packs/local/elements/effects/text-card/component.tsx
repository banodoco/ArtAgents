import type {CSSProperties, ReactElement} from 'react';
import {Img, OffthreadVideo, useCurrentFrame, useVideoConfig} from 'remotion';
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

// Local-pack TextCard: real DOM/text rendering for `clipType: "text"` clips
// (the builtin component is a `() => null` stub awaiting a theme override).
//
// Reads:
//   clip.text         -> {content, subtitle?, fontFamily?, fontSize?, color?, align?, bold?, italic?}
//   clip.params       -> {anchor, offsetX, offsetY, maxWidth,
//                         background, padding, borderRadius, lineHeight, weight,
//                         letterSpacing, textShadow,
//                         subtitle styling (subtitleColor, subtitleFontSize,
//                         subtitleWeight, subtitleLetterSpacing, subtitleTransform,
//                         subtitleSpacing),
//                         decorator: "bar"|"dot"|"none", accent}
//   clip.effects      -> {fade_in?, fade_out?, slide_in?: px, slide_out?: px}
//   clip.x/y/width/height -> manual absolute positioning (canvas px); wins over anchor
//   clip.hold         -> clip duration (seconds)
//
// `anchor` ∈ {top-left, top, top-right, left, center, right,
//             bottom-left, bottom, bottom-right}
// `offsetX/offsetY` are inset px from the anchor edge(s).

type TextData = {
  content?: string;
  fontFamily?: string;
  fontSize?: number;
  color?: string;
  align?: 'left' | 'center' | 'right';
  bold?: boolean;
  italic?: boolean;
};

type CardParams = {
  // Subtitle (small label rendered above or below content). Lives in
  // params, not in `text`, because the timeline-schema's `text` object
  // enforces additionalProperties: false and only allows the known fields
  // above.
  subtitle?: string;
  subtitlePosition?: 'above' | 'below';
  // Reserved horizontal space (px) on the left of the panel for a sprite
  // / icon overlay added later. Renders as inline padding on the card.
  spriteSpace?: number;
  anchor?: Anchor;
  offsetX?: number;
  offsetY?: number;
  maxWidth?: number;
  // Card wrapper styling — applies to a wrapper div that holds BOTH the
  // subtitle and the content, so a panel reads as one unit.
  background?: string;
  padding?: number | string;
  borderRadius?: number | string;
  border?: string;
  borderLeft?: string;
  backdropFilter?: string;
  boxShadow?: string;
  lineHeight?: number;
  weight?: number;
  letterSpacing?: number | string;
  textShadow?: string;
  // Subtitle (small label rendered above content) styling:
  subtitleColor?: string;
  subtitleFontSize?: number;
  subtitleWeight?: number;
  subtitleLetterSpacing?: number | string;
  subtitleTransform?: 'uppercase' | 'lowercase' | 'capitalize' | 'none';
  subtitleSpacing?: number; // px gap between subtitle and content
  // Decorative accent rendered inline with the subtitle:
  decorator?: 'bar' | 'dot' | 'none';
  accent?: string;
  // CTA / footer block rendered below the content (and below the
  // subtitle when subtitlePosition === 'below'). Used for one-panel
  // title cards that house a headline + slogan + a call-to-action.
  ctaLabel?: string;
  ctaText?: string;
  ctaSpacing?: number;
  ctaDivider?: boolean;
  ctaLabelColor?: string;
  ctaLabelFontSize?: number;
  ctaLabelLetterSpacing?: number | string;
  ctaTextColor?: string;
  ctaTextFontSize?: number;
  ctaTextWeight?: number;
  // Placeholder squares for future sprite/character animation.
  //   topSprite     — centered block ABOVE the content row.
  //   leftSprite    — inline to the LEFT of content, with a mirror spacer.
  //   ctaSprite     — inline to the RIGHT of the CTA text, with a mirror.
  topSpriteSize?: number;
  topSpriteColor?: string;
  topSpriteRadius?: number;
  topSpriteGap?: number;
  // When the topSprite asset is a sprite SHEET (multiple frames packed
  // in a grid), set these so the component cycles through frames using
  // CSS background-position.
  topSpriteCols?: number;
  topSpriteRows?: number;
  topSpriteFrames?: number;
  topSpriteFps?: number;
  leftSpriteSize?: number;
  leftSpriteColor?: string;
  leftSpriteRadius?: number;
  leftSpriteGap?: number;
  ctaSpriteSize?: number;
  ctaSpriteColor?: string;
  ctaSpriteRadius?: number;
  ctaSpriteGap?: number;
};

const flexAlign = (align: 'left' | 'center' | 'right' | undefined): CSSProperties => {
  if (align === 'left') return {textAlign: 'left'};
  if (align === 'right') return {textAlign: 'right'};
  return {textAlign: 'center'};
};

const Decorator = ({kind, color, align}: {
  kind: 'bar' | 'dot' | 'none';
  color: string;
  align: 'left' | 'center' | 'right';
}): ReactElement | null => {
  if (kind === 'none') return null;
  const baseStyle: CSSProperties = {
    display: 'inline-block',
    background: color,
    verticalAlign: 'middle',
    marginRight: align === 'right' ? 0 : 12,
    marginLeft: align === 'right' ? 12 : 0,
  };
  if (kind === 'dot') {
    return <span style={{...baseStyle, width: 6, height: 6, borderRadius: '50%'}} />;
  }
  return <span style={{...baseStyle, width: 22, height: 2, borderRadius: 1}} />;
};

export default function TextCard(
  props: ElementComponentProps,
): ReactElement | null {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const clip = props.clip;
  const text = narrowParams<TextData>(clip.text ?? props.params);
  const card = narrowParams<CardParams>(clip.params ?? props.params);
  const effects = normalizeEffects(clip.effects);

  const content = text.content ?? '';
  const subtitle = card.subtitle;
  // Allow bg-only / blur-only clips: render the panel even with no text,
  // as long as there's a background or backdropFilter to show.
  if (!content && !subtitle && !card.background && !card.backdropFilter) return null;

  const sourceDuration =
    typeof clip.hold === 'number'
      ? clip.hold
      : (clip.to ?? 0) - (clip.from ?? 0);
  const speed = clip.speed ?? 1;
  const durationFrames = Math.max(1, Math.round((sourceDuration / speed) * fps));
  const opacity = fadeOpacity(effects, frame, durationFrames, fps);
  const transform = slideTransform(effects, frame, durationFrames, fps);

  const align = text.align ?? 'left';

  const useManual =
    clip.x !== undefined || clip.y !== undefined ||
    clip.width !== undefined || clip.height !== undefined;

  // Special-case: full-bleed bg/blur with no text. Render a single
  // absolutely-positioned div that fills the manual area, no flex /
  // anchor / inline-block weirdness. Used for outro blur overlays.
  const isFullBleed = useManual && !content && !subtitle;
  if (isFullBleed) {
    return (
      <div
        style={{
          position: 'absolute',
          left: clip.x ?? 0,
          top: clip.y ?? 0,
          width: clip.width,
          height: clip.height,
          background: card.background,
          backdropFilter: card.backdropFilter,
          WebkitBackdropFilter: card.backdropFilter,
          opacity,
          transform,
          pointerEvents: 'none',
        }}
      />
    );
  }

  const anchor: Anchor = card.anchor ?? 'center';
  const offsetX = card.offsetX ?? 0;
  const offsetY = card.offsetY ?? 0;

  const positionStyle: CSSProperties = useManual
    ? {position: 'absolute', left: clip.x, top: clip.y, width: clip.width, height: clip.height}
    : anchorPosition(anchor, offsetX, offsetY);

  // anchorPosition uses `transform: translate(-50%, …)` for center
  // anchors; merge that with the slide animation transform so neither
  // clobbers the other. Without this, slide_in overrides the centering
  // and the card slides to the right of the page.
  const positionTransform = positionStyle.transform as string | undefined;
  const mergedTransform = [positionTransform, transform]
    .filter((t): t is string => Boolean(t))
    .join(' ');

  const containerStyle: CSSProperties = {
    ...positionStyle,
    maxWidth: card.maxWidth,
    opacity,
    transform: mergedTransform || undefined,
    pointerEvents: 'none',
    boxSizing: 'border-box',
  };

  const baseTextShadow = card.textShadow ?? '0 2px 12px rgba(0,0,0,0.85), 0 0 2px rgba(0,0,0,0.7)';
  const accentColor = card.accent ?? card.subtitleColor ?? '#DD4A3A';

  // Card wrapper holds BOTH subtitle and content so they read as a single
  // panel against the source video underneath.
  const cardWrapperStyle: CSSProperties = {
    background: card.background,
    padding: card.padding,
    borderRadius: card.borderRadius,
    border: card.border,
    borderLeft: card.borderLeft,
    backdropFilter: card.backdropFilter,
    WebkitBackdropFilter: card.backdropFilter,
    boxShadow: card.boxShadow,
    boxSizing: 'border-box',
    display: 'inline-block',
    position: 'relative',
  };
  // Only override paddingLeft when sprite space is requested. Setting
  // `paddingLeft: undefined` inline alongside the `padding` shorthand
  // wipes the left value React just set — that was making every panel
  // render with padding-left 0 and padding-right intact, so all text
  // looked nudged to the left of its container.
  if (card.spriteSpace) {
    cardWrapperStyle.paddingLeft =
      (typeof card.padding === 'number' ? card.padding : 28) + card.spriteSpace;
  }

  // Outer alignment container — when the card has a background+padding,
  // we still want the whole panel to sit flush against the anchor edge.
  const alignmentStyle: CSSProperties = {
    ...flexAlign(align),
  };

  const subtitlePosition = card.subtitlePosition ?? 'above';
  const subtitleSpacing = card.subtitleSpacing ?? 8;
  const subtitleStyle: CSSProperties = {
    color: card.subtitleColor ?? accentColor,
    fontFamily: text.fontFamily ?? 'Inter, system-ui, sans-serif',
    fontSize: card.subtitleFontSize ?? Math.max(10, Math.round((text.fontSize ?? 36) * 0.4)),
    fontWeight: card.subtitleWeight ?? 700,
    letterSpacing: card.subtitleLetterSpacing ?? '0.22em',
    textTransform: card.subtitleTransform ?? 'uppercase',
    textShadow: card.background ? undefined : baseTextShadow,
    marginBottom: subtitlePosition === 'above' ? subtitleSpacing : 0,
    marginTop: subtitlePosition === 'below' ? subtitleSpacing : 0,
    ...flexAlign(align),
    whiteSpace: 'normal',
  };

  const contentStyle: CSSProperties = {
    color: text.color ?? '#ffffff',
    fontFamily: text.fontFamily ?? 'Inter, system-ui, sans-serif',
    fontSize: text.fontSize ?? 36,
    fontWeight: card.weight ?? (text.bold ? 700 : 500),
    fontStyle: text.italic ? 'italic' : 'normal',
    lineHeight: card.lineHeight ?? 1.25,
    letterSpacing: card.letterSpacing,
    textShadow: card.background ? undefined : baseTextShadow,
    ...flexAlign(align),
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  };

  const hasCta = Boolean(card.ctaLabel || card.ctaText);
  const hasContentAbove = Boolean(content || subtitle);
  const ctaSpacing = card.ctaSpacing ?? 22;
  const ctaContainerStyle: CSSProperties = {
    marginTop: hasContentAbove ? ctaSpacing : 0,
    paddingTop: hasContentAbove && card.ctaDivider ? ctaSpacing : 0,
    borderTop: hasContentAbove && card.ctaDivider
      ? `1px solid ${(text.color ?? '#161620') + '22'}`
      : undefined,
    ...flexAlign(align),
  };
  const ctaLabelStyle: CSSProperties = {
    color: card.ctaLabelColor ?? accentColor,
    fontFamily: text.fontFamily ?? 'Inter, system-ui, sans-serif',
    fontSize: card.ctaLabelFontSize ?? 12,
    fontWeight: 700,
    letterSpacing: card.ctaLabelLetterSpacing ?? '0.24em',
    textTransform: 'uppercase',
    marginBottom: 6,
    ...flexAlign(align),
  };
  const ctaTextStyle: CSSProperties = {
    color: card.ctaTextColor ?? text.color ?? '#161620',
    fontFamily: text.fontFamily ?? 'Inter, system-ui, sans-serif',
    fontSize: card.ctaTextFontSize ?? 20,
    fontWeight: card.ctaTextWeight ?? 600,
    letterSpacing: '0.04em',
    ...flexAlign(align),
  };

  return (
    <div style={containerStyle}>
      <div style={alignmentStyle}>
        <div style={cardWrapperStyle}>
          {card.topSpriteSize ? (() => {
            const spriteUrl = props.assetEntry?.file ?? props.assetEntry?.url;
            const wrapper: CSSProperties = {
              width: card.topSpriteSize,
              height: card.topSpriteSize,
              borderRadius: card.topSpriteRadius ?? 8,
              margin: `0 auto ${card.topSpriteGap ?? 18}px`,
              overflow: 'hidden',
              imageRendering: 'pixelated',
            };
            // Sprite sheet (PNG with grid of frames) — universal alpha
            // support via PNG transparency, cycle frames via CSS
            // background-position keyed off useCurrentFrame.
            if (spriteUrl && /\.(png|jpe?g|webp|gif|avif)(\?|$)/i.test(spriteUrl) && card.topSpriteCols && card.topSpriteRows) {
              const cols = card.topSpriteCols;
              const rows = card.topSpriteRows;
              const totalFrames = card.topSpriteFrames ?? cols * rows;
              const spriteFps = card.topSpriteFps ?? 8;
              const frameIndex = Math.floor((frame / fps) * spriteFps) % totalFrames;
              const col = frameIndex % cols;
              const row = Math.floor(frameIndex / cols);
              const xPct = cols > 1 ? (col / (cols - 1)) * 100 : 0;
              const yPct = rows > 1 ? (row / (rows - 1)) * 100 : 0;
              return (
                <div
                  style={{
                    ...wrapper,
                    backgroundImage: `url(${spriteUrl})`,
                    backgroundSize: `${cols * 100}% ${rows * 100}%`,
                    backgroundPosition: `${xPct}% ${yPct}%`,
                    backgroundRepeat: 'no-repeat',
                  }}
                />
              );
            }
            if (spriteUrl && /\.(mp4|webm|mov)(\?|$)/i.test(spriteUrl)) {
              return (
                <div style={wrapper}>
                  <OffthreadVideo
                    src={spriteUrl}
                    muted
                    style={{width: '100%', height: '100%', objectFit: 'contain'}}
                  />
                </div>
              );
            }
            if (spriteUrl && /\.(png|jpe?g|webp|gif|avif)(\?|$)/i.test(spriteUrl)) {
              return (
                <div style={wrapper}>
                  <Img
                    src={spriteUrl}
                    style={{width: '100%', height: '100%', objectFit: 'contain'}}
                    crossOrigin="anonymous"
                  />
                </div>
              );
            }
            // Fallback: black placeholder square
            return (
              <div
                style={{
                  ...wrapper,
                  background: card.topSpriteColor ?? '#0a0a14',
                }}
              />
            );
          })() : null}
          {subtitle && subtitlePosition === 'above' ? (
            <div style={subtitleStyle}>
              <Decorator
                kind={card.decorator ?? 'bar'}
                color={accentColor}
                align={align}
              />
              {subtitle}
            </div>
          ) : null}
          {content ? (
            card.leftSpriteSize ? (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: card.leftSpriteGap ?? 18,
                }}
              >
                {(() => {
                  const spriteUrl = props.assetEntry?.file ?? props.assetEntry?.url;
                  const isImage = !!spriteUrl && /\.(png|jpe?g|webp|gif|avif)(\?|$)/i.test(spriteUrl);
                  const spriteBox: CSSProperties = {
                    width: card.leftSpriteSize,
                    height: card.leftSpriteSize,
                    borderRadius: card.leftSpriteRadius ?? 6,
                    flexShrink: 0,
                    overflow: 'hidden',
                  };
                  return isImage ? (
                    <div style={spriteBox}>
                      <Img
                        src={spriteUrl}
                        crossOrigin="anonymous"
                        style={{width: '100%', height: '100%', objectFit: 'cover'}}
                      />
                    </div>
                  ) : (
                    <div
                      style={{
                        ...spriteBox,
                        background: card.leftSpriteColor ?? '#0a0a14',
                      }}
                    />
                  );
                })()}
                <div style={contentStyle}>{content}</div>
                <div
                  style={{
                    width: card.leftSpriteSize,
                    flexShrink: 0,
                    visibility: 'hidden',
                  }}
                />
              </div>
            ) : (
              <div style={contentStyle}>{content}</div>
            )
          ) : null}
          {subtitle && subtitlePosition === 'below' ? (
            <div style={subtitleStyle}>{subtitle}</div>
          ) : null}
          {hasCta ? (
            <div style={ctaContainerStyle}>
              {card.ctaLabel ? <div style={ctaLabelStyle}>{card.ctaLabel}</div> : null}
              {card.ctaText ? (
                card.ctaSpriteSize ? (() => {
                  const ctaUrl = !card.topSpriteSize
                    ? props.assetEntry?.file ?? props.assetEntry?.url
                    : undefined;
                  const ctaIsImage = !!ctaUrl && /\.(png|jpe?g|webp|gif|svg|avif)(\?|$)/i.test(ctaUrl);
                  const spriteBox: CSSProperties = {
                    width: card.ctaSpriteSize,
                    height: card.ctaSpriteSize,
                    flexShrink: 0,
                    borderRadius: card.ctaSpriteRadius ?? 4,
                    overflow: 'hidden',
                  };
                  return (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: card.ctaSpriteGap ?? 12,
                      }}
                    >
                      <div
                        style={{
                          width: card.ctaSpriteSize,
                          flexShrink: 0,
                          visibility: 'hidden',
                        }}
                      />
                      <div style={ctaTextStyle}>{card.ctaText}</div>
                      {ctaUrl && ctaIsImage ? (
                        <div style={spriteBox}>
                          <Img
                            src={ctaUrl}
                            crossOrigin="anonymous"
                            style={{width: '100%', height: '100%', objectFit: 'contain'}}
                          />
                        </div>
                      ) : (
                        <div
                          style={{
                            ...spriteBox,
                            background: card.ctaSpriteColor ?? '#0a0a14',
                          }}
                        />
                      )}
                    </div>
                  );
                })() : (
                  <div style={ctaTextStyle}>{card.ctaText}</div>
                )
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
