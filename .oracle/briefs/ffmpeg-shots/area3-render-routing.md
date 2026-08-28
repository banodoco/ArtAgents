# AREA 3: When should we use Remotion vs ffmpeg? What's the render routing architecture?

Explore the render backend selection in /Users/peteromalley/Documents/reigh-workspace/Astrid-megado.

Find:
1. How does `timelines render` choose between backends? Is there a backend registry?
2. Is there already an ffmpeg-only backend alongside the Remotion backend?
3. What determines whether the Remotion adapter is used vs a simpler renderer?
4. Are there other render backends registered (e.g. blender, html-canvas)?
5. What's the interface a render backend must implement? Can we add an ffmpeg backend?

Report verified facts with file:line evidence. <300 words.
