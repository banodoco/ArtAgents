// Self-hosted font loading via CSS @font-face — zero network requests to Google Fonts CDN.
// Font files are committed in remotion/public/fonts/ and served by Remotion's static file server.
// The @font-face declarations are injected as a <style> tag by the FontProvider component.
// This component must be rendered inside the composition (it returns a <style> element).

import {staticFile} from 'remotion';
import React from 'react';

const FACES: {family: string; file: string; weight: string}[] = [
  {family: 'Inter', file: 'fonts/Inter-Regular.woff2', weight: '400'},
  {family: 'Inter', file: 'fonts/Inter-Bold.woff2', weight: '700'},
  {family: 'JetBrains Mono', file: 'fonts/JetBrainsMono-Regular.woff2', weight: '400'},
  {family: 'JetBrains Mono', file: 'fonts/JetBrainsMono-Bold.woff2', weight: '700'},
];

export const FontProvider: React.FC = () => {
  const css = FACES.map(
    ({family, file, weight}) =>
      `@font-face { font-family: '${family}'; src: url('${staticFile(file)}') format('woff2'); font-weight: ${weight}; font-display: block; }`,
  ).join('\n');
  return <style>{css}</style>;
};
