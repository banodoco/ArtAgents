// Self-hosted font loading — ZERO network requests at render time.
// Font files are committed in remotion/public/fonts/ and served by Remotion's
// static file server. Uses @remotion/fonts loadFont() which registers fonts
// via the FontFace API (synchronous from Remotion's perspective — it blocks
// until ready via delayRender internally).

import {staticFile} from 'remotion';
import {loadFont} from '@remotion/fonts';

loadFont({
  family: 'Inter',
  url: staticFile('fonts/Inter-Regular.woff2'),
  weight: '400',
});
loadFont({
  family: 'Inter',
  url: staticFile('fonts/Inter-Bold.woff2'),
  weight: '700',
});
loadFont({
  family: 'JetBrains Mono',
  url: staticFile('fonts/JetBrainsMono-Regular.woff2'),
  weight: '400',
});
loadFont({
  family: 'JetBrains Mono',
  url: staticFile('fonts/JetBrainsMono-Bold.woff2'),
  weight: '700',
});
