import {
  cancelRender,
  continueRender,
  delayRender,
  staticFile,
} from "remotion";
import { createElement, useEffect, useState, type ReactElement } from "react";

/**
 * Fonts that are currently approved and shipped with this checkout.
 *
 * Sixtyfour is intentionally not listed until a redistributable local face
 * and its provenance are reviewed. The 2RP theme still names it, so the
 * Stage 1 offline-render capability must remain blocked until that decision
 * is made; it must never fall back to a hosted Google-font request.
 */
export const LOCAL_FONT_FACES = [
  { family: "Inter", file: "fonts/Inter-Regular.woff2", weight: 400 },
  { family: "Inter", file: "fonts/Inter-Bold.woff2", weight: 700 },
  {
    family: "JetBrains Mono",
    file: "fonts/JetBrainsMono-Regular.woff2",
    weight: 400,
  },
  {
    family: "JetBrains Mono",
    file: "fonts/JetBrainsMono-Bold.woff2",
    weight: 700,
  },
] as const;

export const getLocalFontFaceCss = (): string =>
  LOCAL_FONT_FACES.map(
    ({ family, file, weight }) =>
      `@font-face { font-family: '${family}'; src: url('${staticFile(file)}') format('woff2'); font-weight: ${weight}; font-style: normal; font-display: block; }`,
  ).join("\n");

/**
 * Inject local @font-face declarations and hold Remotion until each shipped
 * face has been loaded. A failed local load cancels the render rather than
 * silently rendering with a system fallback.
 */
export const FontProvider = (): ReactElement => {
  const [renderHandle] = useState(() =>
    delayRender("Loading Astrid local fonts"),
  );

  useEffect(() => {
    let cancelled = false;
    const loadFonts = async (): Promise<void> => {
      try {
        if (typeof document === "undefined" || !document.fonts) {
          throw new Error(
            "Astrid local fonts require the browser FontFaceSet API",
          );
        }

        await Promise.all(
          LOCAL_FONT_FACES.map(({ family, weight }) =>
            document.fonts.load(`${weight} 16px "${family}"`, "Astrid"),
          ),
        );

        const missing = LOCAL_FONT_FACES.filter(
          ({ family, weight }) =>
            !document.fonts.check(`${weight} 16px "${family}"`, "Astrid"),
        );
        if (missing.length > 0) {
          throw new Error(
            `Astrid local font load incomplete: ${missing.map(({ family, weight }) => `${family}/${weight}`).join(", ")}`,
          );
        }

        if (!cancelled) {
          continueRender(renderHandle);
        }
      } catch (error) {
        if (!cancelled) {
          cancelRender(
            error instanceof Error ? error : new Error(String(error)),
          );
        }
      }
    };

    void loadFonts();
    return () => {
      cancelled = true;
    };
  }, [renderHandle]);

  return createElement(
    "style",
    { "data-astrid-local-fonts": true },
    getLocalFontFaceCss(),
  );
};
