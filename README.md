# banodoco-workspace

Development workspace for Banodoco's community projects. Clone this repo, then clone the component repos into it.

## Prerequisites

- Git
- Node.js + npm
- Python 3.10+
- [Supabase CLI](https://supabase.com/docs/guides/cli)

## Setup

```bash
# 1. Clone the workspace
git clone https://github.com/banodoco/banodoco-workspace.git
cd banodoco-workspace

# 2. Clone the component repos
git clone https://github.com/banodoco/ados.git
git clone https://github.com/banodoco/brain-of-bndc.git
git clone https://github.com/banodoco/arca-gidan.git
git clone https://github.com/banodoco/Banodoco-website.git banodoco-website
git clone https://github.com/banodoco/artcompute.git
```

Your workspace should look like this:

```
banodoco-workspace/
  ados/       ADOS event site (React/Vite) — ados.events
  brain-of-bndc/      BNDC community bot (Python) — Discord bot for knowledge sharing
  arca-gidan/         Arca Gidan Prize site (React/Vite) — open source AI art award
  artcompute/         ArtCompute (React/Vite)
  banodoco-website/   Banodoco main site (React/Vite) — banodoco.ai
  structure.md        Cross-project architecture overview
  docs/               Debugging guide and credentials reference
```

## Repo Setup

**ados** (ADOS event site):
```bash
cd ados
npm install
npm run dev
```

**brain-of-bndc** (Discord bot):
```bash
cd brain-of-bndc
pip install -r requirements.txt
# Set up .env with Discord + Supabase credentials
python main.py
```

**arca-gidan** (Arca Gidan Prize):
```bash
cd arca-gidan
npm install
npm run dev
```

**artcompute** (ArtCompute):
```bash
cd artcompute
npm install
npm run dev
```

**banodoco-website** (main site):
```bash
cd banodoco-website
npm install
npm run dev
```

## Database Migrations

All shared Supabase migrations belong in `banodoco-workspace/supabase/`. Treat that workspace-level directory as the only schema source of truth for the shared Banodoco database.

Run database pushes from the workspace root:

```bash
cd banodoco-workspace
supabase db push
```

The app repos (`brain-of-bndc/`, `arca-gidan/`, `banodoco-website/`, and `ados/`) are Supabase clients only. Keep their environment variables and client configuration there, but do not add or run app-local migration chains.

## Key Docs

| Doc | Purpose |
|-----|---------|
| [structure.md](structure.md) | How the five repos fit together — architecture, data flow, shared database |
| [docs/debugging.md](docs/debugging.md) | When something breaks — decision table, blast radius, gotchas |
| [docs/credentials.md](docs/credentials.md) | Where to get every API key and credential |
