# S3 — Scoped-config primitive + themes

**Context:** RFC §3 + MIGRATION-PLAN. **Profile:** partnered / full / depth high. Depends on S1; de-risked by S0.

## Outcome
Ambient context is a first-class **scoped-config** primitive resolved by the kernel per scope (project/user/env) — not module-global state + env threading. Themes reimplemented on it; secrets folded in.

## Scope (IN)
1. **Scoped-config primitive** — kernel-resolved typed config keyed by scope; distinct from per-call `params` and from dataflow artifacts. Capabilities declare which scoped configs they accept; the kernel injects them. (Use the S0 prototype as the proven shape.)
2. **Kill the globals** — remove `_ACTIVE_THEME_DIR` + `set_active_theme` and the `HYPE_ACTIVE_THEME`/`ACTIVE_THEME_ENV` threading (the 32+ sites: `env_vars`, `subprocess_env`, `project/run`, `executor/runner`, `hype/parser`). Theme resolution → kernel scope resolution.
3. **`theme.json` → `style_config` scoped artifact** — visual/generation/voice/audio/pacing config becomes typed scoped config consumers declare. Theme element-overrides route through the kernel `OverrideStore`.
4. **Secrets** — `FAL_KEY` et al. become scoped config (credential scope), not implicit env reads.

## Anti-scope (OUT)
No registry collapse (S4). Keep the theme concept/CLI surface; only its implementation changes. Don't generalize to brand-kits/locale yet — prove the primitive on themes+secrets.

## Done / GATE (parity oracle)
Same project resolves to the same elements + config + assets pre/post; subprocess-env parity. All theme/render tests green. No remaining reader of `_ACTIVE_THEME_DIR` or the raw env var.
