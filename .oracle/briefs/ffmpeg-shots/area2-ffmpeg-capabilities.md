# AREA 2: What can ffmpeg do natively for our use case?

Explore the current video pipeline in /Users/peteromalley/Documents/reigh-workspace/astrid-intro-projects/astrid-intro/build/ and the Remotion setup in /Users/peteromalley/Documents/reigh-workspace/Astrid-megado.

Find:
1. What the current render actually produces: extract a frame and check if it's just a static image with text overlay, or if there's any motion/animation
2. What ffmpeg commands would replicate the current output: concat images + drawtext for captions + amix for audio
3. Are there ANY Remotion features being used that ffmpeg can't do? (spring animations, code-driven text, dynamic layout, etc.)
4. What's the ffmpeg command for: show image for N seconds + overlay text at bottom + play audio, in a single command
5. Check if there are any existing ffmpeg-based renderers in the Astrid codebase (search for ffmpeg in astrid/packs/)

Report concrete ffmpeg commands. <300 words.
