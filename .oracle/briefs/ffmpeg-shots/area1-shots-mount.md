# AREA 1: Astrid shots mount — full API and data model

Explore the `timelines shots` mount in the Astrid repo at /Users/peteromalley/Documents/reigh-workspace/Astrid-megado (branch megado/oracle-run-storyboard).

Find:
1. The ShotRepository data model: what fields does a shot have? What does a shot item look like? How do shots relate to timelines?
2. The ShotsService API: create, add_item, remove_item, reorder, list, show — exact method signatures and required fields
3. How shots map to timeline clips: is there a shots→clips bridge? Does the compiler use shots? Or are shots a separate organizational layer?
4. Can a shot have multiple media items (image + audio)? Or is it one item per shot?
5. What happens when you render a timeline that has shots registered? Does the renderer use them?
6. Are shots stored in the SQLite kernel? What tables?

Report verified facts with file:line evidence. <300 words.
