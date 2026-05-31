import type {ReactElement} from 'react';
import {AbsoluteFill} from 'remotion';
import {narrowParams} from '../../_shared/contracts';
import type {ElementComponentProps} from '../../_shared/contracts';

// Minimal default text card. Themes are expected to override this with richer
// typography, but the builtin renders visible markup so a stripped theme still
// produces a readable caption instead of an empty frame. The shape mirrors the
// element.yaml manifest: `content` (required) and `align` (left/center/right).
type TextCardParams = {
  content?: string;
  align?: 'left' | 'center' | 'right';
};

export default function TextCard(
  props: ElementComponentProps,
): ReactElement | null {
  const params = narrowParams<TextCardParams>(props.params);
  const content = typeof params.content === 'string' ? params.content : '';
  if (!content) {
    return null;
  }
  const align: 'left' | 'center' | 'right' = params.align ?? 'center';
  const horizontal =
    align === 'left'
      ? 'flex-start'
      : align === 'right'
        ? 'flex-end'
        : 'center';
  return (
    <AbsoluteFill
      style={{
        justifyContent: 'center',
        alignItems: horizontal,
        padding: '6%',
      }}
    >
      <div
        style={{
          color: '#ffffff',
          fontSize: 64,
          lineHeight: 1.1,
          textAlign: align,
          whiteSpace: 'pre-wrap',
        }}
      >
        {content}
      </div>
    </AbsoluteFill>
  );
}
