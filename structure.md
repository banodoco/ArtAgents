# Banodoco: Project Structure

> **How to Use This Guide**
> - Start here to understand how the five projects relate
> - Each repo has its own README for repo-specific detail
> - For debugging, see [docs/debugging.md](docs/debugging.md)
> - For credentials, see [docs/credentials.md](docs/credentials.md)
> - Source of truth is always the code

---

## Overview

Banodoco is a community focused on open-source AI art. These five projects serve different parts of that mission:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         banodoco-workspace                              │
├──────────┬───────────────┬──────────────┬────────────┬─────────────────┤
│  ados/   │ brain-of-     │ arca-gidan/  │ artcompute/│ banodoco-       │
│          │ bndc/         │              │            │ website/        │
│  ADOS    │ BNDC          │ Arca Gidan   │ ArtCompute │ Banodoco        │
│  event   │ Discord bot   │ Prize site   │ Grants     │ main site       │
│  site    │ (Python)      │ (React/Vite) │ (React/    │ (React/Vite)    │
│ (React/  │               │              │  Vite)     │                 │
│  Vite)   │               │              │            │                 │
└────┬─────┴───────┬───────┴──────┬───────┴─────┬──────┴────────┬────────┘
     │             │              │             │               │
     │             │              │             │               │
     └─────────────┼──────────────┘             │               │
                   │                            │               │
            ┌──────┴──────┐              ┌──────┴──────┐        │
            │  Supabase   │◄─────────────│ Solana RPC  │        │
            │  (shared)   │              │ + CoinGecko │        │
            └─────────────┘              └─────────────┘        │
                   ▲                                            │
                   └────────────────────────────────────────────┘
```

---

## Tech Stack

| Project | Stack | Hosting | URL | Repo |
|---------|-------|---------|-----|------|
| **ADOS** | React 18 + Vite + TypeScript + Framer Motion | Static site | [ados.events](https://ados.events) | [banodoco/ados](https://github.com/banodoco/ados) |
| **BNDC** | Python 3.10 + Supabase + Claude API | Railway (Docker) | Discord bot | [banodoco/brain-of-bndc](https://github.com/banodoco/brain-of-bndc) |
| **Arca Gidan** | React 18 + Vite + TypeScript | Nixpacks | TBD | [banodoco/arca-gidan](https://github.com/banodoco/arca-gidan) |
| **ArtCompute** | React 19 + Vite + TypeScript + Tailwind | Static site | TBD | [banodoco/artcompute](https://github.com/banodoco/artcompute) |
| **Banodoco Website** | React 19 + Vite + TypeScript + Tailwind | Static site | [banodoco.ai](https://banodoco.ai) | [banodoco/Banodoco-website](https://github.com/banodoco/Banodoco-website) |

---

## Project Descriptions

### ados — ADOS Event Site
The Open Source AI Art Weekend. A single-page event site with animated hero, invite system (personalized via Discord ID), circular gallery, and poster scroll sections. Pulls invite data from Supabase `members` via REST API. Supabase credentials are hardcoded (no env vars).

### brain-of-bndc — BNDC's Brain
A Discord bot dedicated to helping the Banodoco and open source AI art communities. Key features:
- **Summarizing**: Daily Claude-generated summaries of Discord activity
- **Archiving**: Searchable message archive in Supabase
- **Curating**: Auto-identifies high-quality posts
- **Gating**: Intro approval system for new members
- **Sharing**: Social posting to Twitter, TikTok, Instagram, YouTube (via Zapier)
- **Grants**: Grant assessment and tracking

Runs on Railway with health checks at `/health`, `/ready`, `/status` on port 8080.

### arca-gidan — Arca Gidan Prize
An award site for open source AI art. Features competition management, submission system, voting with fraud detection, Discord OAuth, and admin tools. Uses Supabase for auth and data.

### artcompute — ArtCompute
Grant fund display. Reads Solana wallet balance and SOL/USD price from public APIs (no Supabase, no env vars). Standalone — no cross-repo dependencies.

### banodoco-website — Banodoco Main Site
The official website at banodoco.ai. Presents the organization's mission, projects, and community. Pulls live community topics from Supabase `daily_summaries` (gracefully degrades if Supabase is unavailable).

### effects — Shared Render Effects
Workspace-level Remotion visual effects. Each direct child directory is an effect id and contains the effect component plus schema, defaults, and metadata used by the tools render-time catalog.

### themes — Shared Render Themes
Workspace-level Remotion design tokens. Themes provide color, type, and motion values to render effects so source-cut and generative videos share one visual system.

---

## Shared Infrastructure

### Supabase (shared database)

All projects except artcompute share one Supabase instance. brain-of-bndc is the primary operational writer; arca-gidan writes prize-competition data. The schema source of truth belongs at the workspace level so every app targets the same migration chain.

| Table | Writer | Reader(s) | Purpose |
|-------|--------|-----------|---------|
| `members` | brain-of-bndc | ados, arca-gidan, banodoco-website | Shared member profiles, avatars, auth linkage, Banodoco roles |
| `guild_members` | brain-of-bndc | brain-of-bndc | Per-server membership + speaker/monitor state |
| `daily_summaries` | brain-of-bndc | banodoco-website | Claude-generated community summaries |
| `discord_messages` | brain-of-bndc | brain-of-bndc, banodoco-website | Archived Discord messages |
| `discord_channels` | brain-of-bndc | banodoco-website | Channel metadata |
| `media` | brain-of-bndc, banodoco-website, arca-gidan | arca-gidan, banodoco-website | Shared uploaded art/media records |
| `assets` | brain-of-bndc, banodoco-website, arca-gidan | arca-gidan, banodoco-website | Shared workflows, LoRAs, and downloadable resources |
| `asset_media` | arca-gidan, banodoco-website | arca-gidan, banodoco-website | Links assets to media previews |
| `posts` | brain-of-bndc, future shared editors | brain-of-bndc | Long-form shared content that can be entered into competitions |
| `competitions` | arca-gidan (admin) | arca-gidan | Prize competitions for Arca Gidan |
| `discord_competitions` | brain-of-bndc (admin) | brain-of-bndc | Discord-native community competitions run by the bot |
| `competition_entries` | arca-gidan (users), brain-of-bndc | arca-gidan, brain-of-bndc | Unified prize submissions + Discord competition entries |
| `scores` | arca-gidan (users) | arca-gidan | 1-10 scoring with confidence weighting + fraud detection. See arca-gidan README for full scoring methodology. |
| `votes` | (legacy, Edition 1) | arca-gidan | Binary votes from Edition 1, migrated into `scores` as score=10. Kept for historical reference. |
| `server_config` | brain-of-bndc (admin) | brain-of-bndc | Per-guild settings, `write_enabled` flag |
| `grant_applications` | brain-of-bndc | artcompute (display) | Grant tracking |

Shared migrations live in `banodoco-workspace/supabase/migrations/`. Individual repos keep only client config such as env vars and Supabase client setup.

This consolidation avoids schema drift between apps. If multiple repos share one Supabase project, only one migration directory should own DDL, triggers, RLS policies, and storage setup.

### Discord
- brain-of-bndc operates in the Banodoco Discord server
- ados uses Discord member IDs for personalized invites
- arca-gidan uses Discord OAuth for authentication

### External APIs
- **Claude API** (Anthropic): brain-of-bndc uses for summaries
- **Solana RPC**: artcompute reads wallet balance
- **CoinGecko**: artcompute reads SOL/USD price
- **Twitter/X, Zapier**: brain-of-bndc optional social sharing

### GitHub
All repos under [github.com/banodoco](https://github.com/banodoco).

---

## Key Docs

| Doc | Purpose |
|-----|---------|
| [docs/debugging.md](docs/debugging.md) | When something breaks — decision table, blast radius, gotchas |
| [docs/credentials.md](docs/credentials.md) | Where to get every API key and credential |
