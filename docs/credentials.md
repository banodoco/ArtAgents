# Credentials Reference

> Where to get every API key. Each repo has its own `.env` file — copy from the example, fill in the values.

---

## Env Files

| Repo | Template | Live file |
|------|----------|-----------|
| **brain-of-bndc** | `.env.example` | `brain-of-bndc/.env` |
| **arca-gidan** | `.env.example` | `arca-gidan/.env.local` |
| **banodoco-website** | `.env.example` | `banodoco-website/.env` |
| **ados** | (none — hardcoded in `src/pages/Index.tsx`) | — |
| **artcompute** | (none — uses public APIs) | — |

All `.env` files are gitignored at the workspace level.

---

## Supabase (brain-of-bndc, arca-gidan, banodoco-website, ados)

**Dashboard:** https://supabase.com/dashboard → select your project → Project Settings > API

| Env Var | Where to Find | Notes |
|---------|--------------|-------|
| `SUPABASE_URL` / `VITE_SUPABASE_URL` | Project Settings > API > Project URL | Same across all repos |
| `VITE_SUPABASE_ANON_KEY` | Project Settings > API > `anon` `public` key | Safe for client-side, respects RLS |
| `SUPABASE_SERVICE_KEY` | Project Settings > API > `service_role` key | **Server-side only** (brain-of-bndc). Bypasses RLS. |
| `SUPABASE_DB_PASSWORD` | Project Settings > Database > Connection string | Set at project creation, can be reset |

**Note:** ADOS has Supabase credentials hardcoded in `src/pages/Index.tsx` rather than using env vars.

---

## Discord (brain-of-bndc)

### Bot Token

**Portal:** https://discord.com/developers/applications

1. Create or select an application
2. Go to **Bot** in the sidebar
3. Click **Reset Token** to generate the token → `DISCORD_BOT_TOKEN`
4. Enable under **Privileged Gateway Intents**: Message Content, Server Members, Presence
5. Go to **OAuth2 > URL Generator**, select `bot` scope, choose permissions (Send Messages, Read Message History, Manage Messages, Add Reactions, Manage Threads), use the URL to invite to your server

### IDs

Enable **Developer Mode**: User Settings > App Settings > Advanced > Developer Mode. Then right-click to copy IDs.

| Env Var | How to Get |
|---------|-----------|
| `GUILD_ID` / `DEV_GUILD_ID` | Right-click server name > Copy Server ID |
| `SUMMARY_CHANNEL_ID`, `ART_CHANNEL_ID`, `TOP_GEN_CHANNEL`, `TEST_DATA_CHANNEL` | Right-click channel > Copy Channel ID |
| `ADMIN_USER_ID`, `BOT_USER_ID` | Right-click user > Copy User ID |
| `CURATOR_IDS` | Comma-separated user IDs |
| `SPEAKER_ROLE_ID`, `APPROVER_ROLE_ID`, `SUPER_APPROVER_ROLE_ID`, `NO_SHARING_ROLE_ID` | Server Settings > Roles > right-click role > Copy Role ID |
| `GATE_CHANNEL_ID`, `INTRO_CHANNEL_ID` | Right-click channel > Copy Channel ID |
| `CHANNELS_TO_MONITOR` | Comma-separated channel IDs |

---

## Anthropic Claude API (brain-of-bndc)

**Console:** https://console.anthropic.com/settings/keys

1. Sign up / log in
2. Go to **API Keys**
3. Click **Create Key** → `ANTHROPIC_API_KEY`

Requires a payment method. Pay-per-token.

---

## OpenAI API (brain-of-bndc, optional)

**Dashboard:** https://platform.openai.com/api-keys

1. Sign up / log in
2. Click **Create new secret key** → `OPENAI_API_KEY`

Requires a payment method.

---

## Twitter / X API (brain-of-bndc, optional)

**Portal:** https://developer.x.com/en/portal/dashboard

1. Sign up for a developer account (requires approval)
2. Create a Project and App
3. Under **Keys and tokens**, generate:

| Env Var | Twitter Name |
|---------|-------------|
| `TWITTER_CONSUMER_KEY` | API Key |
| `TWITTER_CONSUMER_SECRET` | API Key Secret |
| `TWITTER_ACCESS_TOKEN` | Access Token |
| `TWITTER_ACCESS_TOKEN_SECRET` | Access Token Secret |

4. Set permissions to **Read and Write** under App Settings > User authentication settings

**Note:** Free tier is very limited. Posting requires at minimum the Basic plan ($100/month).

---

## Railway (brain-of-bndc hosting)

**Dashboard:** https://railway.com/

1. Sign up / log in
2. Create a new project, connect the GitHub repo (`banodoco/brain-of-bndc`)
3. Add a service from the repo
4. Set all environment variables in the service's **Variables** tab

Railway auto-provides: `RAILWAY_DEPLOYMENT_ID`, `RAILWAY_SERVICE_ID`, `RAILWAY_REPLICA_ID`, `PORT`

---

## Zapier Webhooks (brain-of-bndc, optional)

**Dashboard:** https://zapier.com/

1. Create a new Zap with **Webhooks by Zapier** as the trigger (choose "Catch Hook")
2. Zapier provides a unique webhook URL for each Zap
3. Copy the URLs into:

| Env Var | Purpose |
|---------|---------|
| `ZAPIER_TIKTOK_BUFFER_URL` | Forwards to TikTok (via Buffer) |
| `ZAPIER_INSTAGRAM_URL` | Forwards to Instagram |
| `ZAPIER_YOUTUBE_URL` | Forwards to YouTube |

Free plan: 100 tasks/month.

---

## Public APIs (no keys needed)

| Service | Used By | Endpoint | Notes |
|---------|---------|----------|-------|
| **Solana RPC** | artcompute | `https://solana-rpc.publicnode.com` | Free, rate-limited. Alternatives: Helius, QuickNode, Alchemy |
| **CoinGecko** | artcompute | `https://api.coingecko.com/api/v3/simple/price` | Free, ~10-30 calls/min |

---

## Env Vars by Project (summary)

### brain-of-bndc (many)
See `.env.example` in the repo for the full list with comments.

### arca-gidan
```
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

### banodoco-website
```
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```
Optional — site renders without them (community section shows empty).

### ados
No env vars — Supabase credentials are hardcoded in `src/pages/Index.tsx`.

### artcompute
No env vars — uses public APIs with hardcoded endpoints.
