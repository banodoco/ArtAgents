import type { ComponentType } from 'react';
export type ThemePackageRegistryEntry = {
    component: ComponentType<unknown>;
    themeId: string;
    source: string;
};
export declare const THEME_PACKAGE_CLIP_TYPES: readonly ["art-card", "cta-card", "resource-card", "section-hook"];
export type ThemePackageClipType = typeof THEME_PACKAGE_CLIP_TYPES[number];
export declare const THEME_PACKAGE_REGISTRY: Record<ThemePackageClipType, ThemePackageRegistryEntry>;
//# sourceMappingURL=registry.generated.d.ts.map