import type {ReactElement} from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';

import {
  type ElementComponentProps,
  narrowParams,
} from '../../_shared/contracts';

type ColourEvent = {
  id?: string;
  frame: number;
  color: string;
};

type AudioReactiveColourParams = {
  schemaVersion?: number;
  initialColor?: string;
  events?: ColourEvent[];
};

const HEX_COLOUR = /^#[0-9A-Fa-f]{6}$/;

const normalizedEvents = (value: unknown): ColourEvent[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((event): event is ColourEvent => {
      if (!event || typeof event !== 'object') {
        return false;
      }
      const candidate = event as Partial<ColourEvent>;
      return (
        Number.isInteger(candidate.frame)
        && (candidate.frame ?? 0) >= 1
        && typeof candidate.color === 'string'
        && HEX_COLOUR.test(candidate.color)
      );
    })
    .map((event, sourceIndex) => ({event, sourceIndex}))
    .sort((left, right) => (
      left.event.frame - right.event.frame
      || left.sourceIndex - right.sourceIndex
    ))
    .map(({event}) => event);
};

const activeColour = (
  initialColor: string,
  events: ColourEvent[],
  frame: number,
): string => {
  let low = 0;
  let high = events.length - 1;
  let active = initialColor;
  while (low <= high) {
    const middle = Math.floor((low + high) / 2);
    const event = events[middle];
    if (event.frame <= frame) {
      active = event.color;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  return active;
};

export default function AudioReactiveColour(
  props: ElementComponentProps,
): ReactElement {
  const frame = useCurrentFrame();
  const params = narrowParams<AudioReactiveColourParams>(props.params);
  const initialColor = (
    typeof params.initialColor === 'string'
    && HEX_COLOUR.test(params.initialColor)
  )
    ? params.initialColor
    : '#000000';
  const events = normalizedEvents(params.events);
  const backgroundColor = activeColour(initialColor, events, frame);

  return <AbsoluteFill style={{backgroundColor}} />;
}
