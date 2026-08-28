# EXPLORER BRIEF: reigh-app video editor — shot/sequence/composition data structures

Repo: /Users/peteromalley/Documents/reigh-workspace/reigh-app
Focus: src/tools/video-editor/ (794 files)

We're designing a "storyboard → shots → nested timelines" architecture for the Astrid intro video.
Each shot should have its own internal timeline (a mini-composition that defines what renders during
that shot's duration). We believe reigh-app already has this or something close to it.

Find and report with file:line evidence:

1. **Sequence/Composition data structures**: What is a "sequence" in reigh-app? Is there a nested composition model where a group of clips forms a self-contained sub-timeline? Check `sequence.ts`, `sequences/`, `compositions/`.

2. **Shot or Group concepts**: Is there a "shot", "group", "section", or "scene" concept that groups clips together? Check `clip-types/`, `core/`, `data/`.

3. **Timeline schema**: What is the timeline JSON schema? Does it support nested timelines (a timeline within a timeline)? Check the Zod schemas in `@banodoco/timeline-schema`.

4. **Render pipeline**: How does reigh-app render videos? Does it use Remotion? Does it support nested compositions? Check `render/`, `compositions/TimelineRenderer.tsx`.

5. **Keyframes**: What keyframe system exists? Check `keyframes/`.

6. **Effects**: What effect system exists? Can effects be applied to groups of clips? Check `effects/`.

Report verified facts with file:line evidence. Ranked by relevance to our nested-shot-timeline design. <500 words.
