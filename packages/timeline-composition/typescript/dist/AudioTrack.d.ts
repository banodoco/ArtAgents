import type { FC } from 'react';
import type { AssetRegistryEntry, TimelineClip, TrackDefinition } from './types';
type AudioTrackProps = {
    clip: TimelineClip;
    track: TrackDefinition;
    assetEntry?: AssetRegistryEntry;
    fps: number;
};
export declare const AudioTrack: FC<AudioTrackProps>;
export {};
//# sourceMappingURL=AudioTrack.d.ts.map