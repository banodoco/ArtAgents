import type { ReactNode } from 'react';
export type Theme = {
    id: string;
    visual: {
        color: {
            fg: string;
            bg: string;
            accent: string;
        };
        type: {
            families: {
                heading: string;
                body: string;
                mono?: string;
            };
            size: {
                base: number;
                small: number;
                large: number;
            };
            weight: {
                normal: number;
                bold: number;
            };
            lineHeight: number;
        };
        motion: {
            fadeMs: number;
        };
        canvas: {
            width: number;
            height: number;
            fps: number;
        };
    };
};
export type RuntimeTheme = Theme & {
    color: Theme['visual']['color'];
    type: Theme['visual']['type'];
    motion: Theme['visual']['motion'];
};
export declare const DEFAULT_THEME: Theme;
export declare const ThemeProvider: ({ children, value, }: {
    children: ReactNode;
    value?: Theme;
}) => ReactNode;
export declare const useTheme: () => RuntimeTheme;
//# sourceMappingURL=ThemeContext.d.ts.map