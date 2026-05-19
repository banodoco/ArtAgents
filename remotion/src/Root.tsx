import type {ReactElement} from 'react';
import {Composition} from 'remotion';
import {
  TimelineComposition,
  getTimelineDurationInFrames,
} from '@banodoco/timeline-composition';
import type {TimelineCompositionProps} from '@banodoco/timeline-composition';
import type {
  CanvasOverride,
  TimelineThemeOverrides,
  VisualOverrides,
} from './types.augmentations';
import './fonts';

const DEFAULT_PROPS: TimelineCompositionProps = {
  timeline: {
    theme: 'banodoco-default',
    theme_overrides: {
      visual: {
        canvas: {
          width: 1920,
          height: 1080,
          fps: 30,
        },
      },
    },
    clips: [],
  },
  assets: {
    assets: {},
  },
};

const DEFAULT_CANVAS: CanvasOverride = {width: 1920, height: 1080, fps: 30};

const getCanvas = (props: TimelineCompositionProps): CanvasOverride => {
  const overrides = props.timeline.theme_overrides as
    | TimelineThemeOverrides
    | undefined;
  const visual = overrides?.visual as VisualOverrides | undefined;
  return (
    visual?.canvas ??
    (props.theme?.visual?.canvas as CanvasOverride | undefined) ??
    DEFAULT_CANVAS
  );
};

export const Root = (): ReactElement => {
  return (
    <Composition
      id="TimelineComposition"
      component={TimelineComposition}
      defaultProps={DEFAULT_PROPS}
      calculateMetadata={async ({props}) => {
        const typedProps = props as TimelineCompositionProps;
        const canvas = getCanvas(typedProps);
        const fps = canvas.fps ?? 30;
        return {
          width: canvas.width ?? 1920,
          height: canvas.height ?? 1080,
          fps,
          durationInFrames: getTimelineDurationInFrames(typedProps.timeline, fps),
        };
      }}
    />
  );
};
