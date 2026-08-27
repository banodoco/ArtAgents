// Loads the Google Fonts referenced by themes/2rp/theme.json so that
// theme.type.families.{heading,body,mono} actually resolve at render time.
// Importing this module triggers font loading as a side effect.
// NOTE: loadFont takes (style, options) — style is "normal", options limits weights/subsets.
import {loadFont as loadSixtyfour} from '@remotion/google-fonts/Sixtyfour';
import {loadFont as loadInter} from '@remotion/google-fonts/Inter';
import {loadFont as loadJetBrainsMono} from '@remotion/google-fonts/JetBrainsMono';

loadSixtyfour();
loadInter('normal', {weights: ['400', '700'], subsets: ['latin']});
loadJetBrainsMono('normal', {weights: ['400', '700'], subsets: ['latin']});
