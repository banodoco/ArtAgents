export type RenderBounds = {
    x: number;
    y: number;
    width: number;
    height: number;
};
export type RenderCropValues = {
    cropTop: number;
    cropBottom: number;
    cropLeft: number;
    cropRight: number;
};
export type ViewportMediaLayout = {
    fullBounds: RenderBounds;
    visibleBounds: RenderBounds;
    renderBounds: RenderBounds;
    mediaBounds: RenderBounds;
    cropValues: RenderCropValues;
};
export type IntrinsicMediaSize = {
    width?: number;
    height?: number;
};
export declare const normalizeRenderCropValues: (cropValues?: Partial<RenderCropValues>) => RenderCropValues;
export declare const getVisibleBoundsFromCrop: (fullBounds: RenderBounds, cropValues?: Partial<RenderCropValues>) => RenderBounds;
export declare const getIntrinsicMediaSize: (resolution?: string | null) => IntrinsicMediaSize;
export declare const computeRenderBounds: (bounds: RenderBounds, compositionWidth: number, compositionHeight: number) => RenderBounds;
export declare const hasRenderableBounds: (bounds: RenderBounds) => boolean;
export declare const computeViewportMediaLayout: ({ fullBounds, cropValues, compositionWidth, compositionHeight, intrinsicWidth, intrinsicHeight, }: {
    fullBounds: RenderBounds;
    cropValues?: Partial<RenderCropValues>;
    compositionWidth: number;
    compositionHeight: number;
    intrinsicWidth?: number;
    intrinsicHeight?: number;
}) => ViewportMediaLayout | null;
//# sourceMappingURL=render-bounds.d.ts.map