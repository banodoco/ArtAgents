# Storyboards

`storyboards/astrid-intro.storyboard.json` is the authored input spec for the intro video:
per-section nav state, image variants (asset/gen), VO text + audio asset, provenance.

## Usage
    ASTRID_PROJECTS_ROOT=<root> python3 scripts/build_storyboard.py validate --story <file>
    ASTRID_PROJECTS_ROOT=<root> python3 scripts/build_storyboard.py compile --story <file> \
        --vo-align <plan.json> --out <dir>
    # then: astrid timelines create <slug> --config <compiled timeline.json> --registry <assets.json>
    #       astrid timelines render <slug>

Rules: the storyboard file is an authored INPUT spec (content + provenance); compiled
resolution fields and all durable execution facts live in the kernel timeline (ONE store).
