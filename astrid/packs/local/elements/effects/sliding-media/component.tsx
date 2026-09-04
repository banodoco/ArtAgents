import type {CSSProperties, ReactElement} from 'react';
import {Img, interpolate, OffthreadVideo, useCurrentFrame, useVideoConfig} from 'remotion';
import {
  normalizeEffects,
  slideTransform,
} from '../_shared/clip-effects';
import {
  type ElementComponentProps,
  narrowParams,
} from '../../../../rendering/elements/_shared/contracts';

// Full-screen media clip with the same left/right slide + fade motion used by
// the text-card overlays. Set clipType to "sliding-media" and provide an asset.
type Params = {
  noFadeIn?: boolean;
  noFadeOut?: boolean;
  objectFit?: 'cover' | 'contain';
};

const opacityForSide = (
  duration: number | undefined,
  frame: number,
  durationInFrames: number,
  fps: number,
  side: 'in' | 'out',
): number => {
  if (typeof duration !== 'number' || duration <= 0) {
    return 1;
  }
  const frames = Math.round(duration * fps);
  if (side === 'in') {
    return interpolate(frame, [0, frames], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
  }
  return interpolate(frame, [durationInFrames - frames, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
};

export default function SlidingMedia(props: ElementComponentProps): ReactElement | null {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const params = narrowParams<Params>(props.clip.params ?? props.params);
  const assetEntry = props.assetEntry;
  const url = assetEntry?.file ?? assetEntry?.url;
  if (!url) {
    return null;
  }

  const effects = normalizeEffects(props.clip.effects);
  const durationInFrames = Math.round((props.clip.hold ?? 0) * fps);
  const opacity =
    (params.noFadeIn ? 1 : opacityForSide(effects.fade_in, frame, durationInFrames, fps, 'in')) *
    (params.noFadeOut ? 1 : opacityForSide(effects.fade_out, frame, durationInFrames, fps, 'out'));
  const translate = slideTransform(effects, frame, durationInFrames, fps);

  const objectFit = params.objectFit ?? 'contain';
  const wrapper: CSSProperties = {
    position: 'absolute',
    inset: 0,
    overflow: 'hidden',
    opacity,
    transform: translate,
  };
  const mediaStyle: CSSProperties = {
    width: '100%',
    height: '100%',
    objectFit,
  };

  const isImage = /\.(png|jpe?g|webp|gif|avif)(\?|$)/i.test(url);
  if (isImage) {
    return (
      <div style={wrapper}>
        <Img src={url} style={mediaStyle} crossOrigin="anonymous" />
      </div>
    );
  }

  return (
    <div style={wrapper}>
      <OffthreadVideo src={url} muted style={mediaStyle} />
    </div>
  );
}
