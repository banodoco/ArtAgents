# North Star — Durable Timeline Visualization

A VLM-capable Astrid agent should be able to run one stable command and
understand a project's temporal structure, spatial layering, grouping, visual
progression, source media, and text/speech evidence through an evidence pack
designed specifically for machine vision, without mutating the source timeline
or relying on ad-hoc inspection commands.

The end state is not merely another contact sheet. It is a durable inspection
surface where:

- proportional timing and readable sequence views are both available;
- project, timeline, shot/range, clip-context, asset, timestamp, and
  text/speech scopes explain the same frozen source model;
- visual and textual outputs cannot disagree because they share one normalized
  inspection model and one layout model;
- numbered PNG pages are the primary VLM surface, with large labels, explicit
  reading order, restrained density, and redundant non-color encodings;
- stable ids connect every visual object to the generic reading guide, concise
  Markdown structure, versioned JSON ground truth, and diagnostics;
- every view exposes executable parent/child/sibling/source actions through one
  learned follow-up operation, with qualified ids and no OCR-dependent shell
  commands printed into the image;
- a root snapshot fixes timeline, registry, transcript, and media hashes;
  children retain its id map and never silently read newer project state;
- verified original media is directly inspectable at full resolution and is
  never confused with a thumbnail, generation reference/output, source
  approximation, or rendered sample;
- authored captions, explicit transcript source segments, mapped speech
  occurrences, and uninspected baked-in text remain visibly distinct;
- a serialized view map makes page geometry, visibility, omissions, and
  continuations machine-checkable;
- transitions, effects, overlaps, pinned groups, audio, compositor order, and
  missing assets remain visible;
- outputs are deterministic, offline, read-only, and owned by normal Astrid
  project runs;
- clarity is demonstrated through repeated image-only VLM comprehension tests
  with hidden ground truth, not assumed from the existence of an image.

There is no human dashboard, audience switch, generic asset browser, guessed
transcript, implicit refresh, or remote fetch. Future implementation choices
may change, but they must preserve those properties.
