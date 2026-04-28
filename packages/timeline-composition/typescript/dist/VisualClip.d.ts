import type { FC } from 'react';
import type { AssetRegistryEntry, TimelineClip, TrackDefinition } from './types';
type VisualClipProps = {
    clip: TimelineClip;
    track: TrackDefinition;
    assetEntry?: AssetRegistryEntry;
    fps: number;
};
export declare const VisualClip: FC<VisualClipProps>;
export {};
//# sourceMappingURL=VisualClip.d.ts.map