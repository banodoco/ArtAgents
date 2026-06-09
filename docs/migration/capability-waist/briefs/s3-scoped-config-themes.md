# S3 — Scoped-config primitive + themes

**Read first:** RFC (§3 scoped config) + MIGRATION-PLAN. **Profile:** partnered / full / depth high.
**Why:** a genuinely novel cross-cutting primitive threaded through 32+ sites → premium reasoning throughout; high planner depth for the blast radius. Depends on S1 (themes ride the timeline path).

## Outcome
Ambient context is a first-class **scoped-config** primitive resolved by the kernel per scope (project/user/env) — not module-global mutable state and env-var threading. Themes are reimplemented on it; secrets fold in.

## Scope (IN)
1. **Scoped-config primitive.** Kernel-resolved typed config keyed by scope; distinct from per-call `params` and from dataflow artifacts. A capability declares which scoped configs it accepts; the kernel injects them.
2. **Kill the globals.** Remove `_ACTIVE_THEME_DIR` module global + `set_active_theme` (`element/catalog.py:32,59-61`) and the `HYPE_ACTIVE_THEME`/`ACTIVE_THEME_ENV` env threading (`env_vars.py:50`, `subprocess_env.py:77`, `project/run.py:94-99`, `executor/runner.py:375`, `hype/parser.py:196`). Theme resolution becomes kernel scope resolution.
3. **`theme.json` → `style_config` scoped artifact.** The visual/generation/voice/audio/pacing config (`theme/_schema.py:22-167`) becomes a typed scoped config; consumers that need it declare it (no side-channel). Theme **element-overrides** route through the kernel `OverrideStore` (they already are that mechanism, relabeled).
4. **Secrets.** `FAL_KEY` et al. become scoped config (credential scope), not implicit env reads.

## Anti-scope (OUT)
No registry collapse (S4). Keep the theme *concept*/CLI surface; only its *implementation* changes. Don't generalize to brand-kits/locale/etc. now — just prove the primitive on themes+secrets.

## Done criteria / GATE (parity oracle)
Same project resolves to the same elements + config + assets pre/post; subprocess-env parity (child processes see equivalent resolved context). All theme/render tests green. No remaining reader of `_ACTIVE_THEME_DIR` or the raw env var.

## Touchpoints
`element/catalog.py`, `element/registry.py` (theme sources), `theme/*`, `env_vars.py`, `subprocess_env.py`, `project/{project,run}.py`, `executor/runner.py`, `hype/parser.py`, `util/secrets.py`.
