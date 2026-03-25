# Debugging

> When something breaks, start here. Find your symptom, confirm the cause, fix it.

---

## Decision Table

### Something is down

| Symptom | Repo | Confirm With | Next Step |
|---------|------|-------------|-----------|
| Bot not responding in Discord | brain-of-bndc | Railway dashboard, `GET :8080/health` | Check logs for startup errors, verify `DISCORD_BOT_TOKEN` |
| Bot running but not posting summaries | brain-of-bndc | Check Railway logs for Claude errors | Verify `ANTHROPIC_API_KEY`, check `SUMMARY_CHANNEL_ID` exists |
| Bot can't write to DB | brain-of-bndc | Query `server_config` in Supabase | Set `write_enabled = TRUE` for the guild |
| ADOS invites not personalizing | ados | Query `discord_members` for the user | Check hardcoded Supabase creds in `ados/src/pages/Index.tsx` — may have rotated |
| banodoco.ai community section empty | banodoco-website | Query `daily_summaries` in Supabase | Check bot is running + summaries have `included_in_main_summary = true` |
| Arca Gidan login failing | arca-gidan | Supabase Auth > Discord provider | Verify OAuth redirect URLs |
| Arca Gidan submissions/votes missing | arca-gidan | Query tables in Supabase | Check RLS policies, fraud detection thresholds |
| ArtCompute showing no balance | artcompute | curl Solana RPC / CoinGecko endpoints | Public APIs may be rate-limited — wait and retry |

### Build / deploy failures

All four frontends: `npm ci && npm run build`. Check TypeScript errors. Arca Gidan has a validation script: `bash pre-deploy-check.sh`.

Missing env vars: arca-gidan crashes without `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY`. banodoco-website degrades gracefully. ados and artcompute need no env vars.

---

## Bot Health Checks (brain-of-bndc)

The bot exposes three endpoints on port 8080 (Railway uses `/ready`):

| Endpoint | Meaning |
|----------|---------|
| `GET /health` | 200 = process running |
| `GET /ready` | 200 = fully initialized, 503 = still loading cogs |
| `GET /status` | JSON with uptime, messages logged, error count |

Init takes 30-60s after deploy — `/ready` returning 503 during this window is normal.

---

## Debug Tools

| Repo | Tools |
|------|-------|
| **brain-of-bndc** | `python scripts/debug.py` + 26 scripts in `scripts/` (archive, backfill, digest, etc.) |
| **arca-gidan** | `bash pre-deploy-check.sh` (pre-deploy validation) |
| **ados, artcompute, banodoco-website** | None |

### Useful Supabase queries

```sql
-- Bot writes enabled?
SELECT * FROM server_config WHERE guild_id = 'YOUR_GUILD_ID';

-- Recent summaries
SELECT date, channel_id, included_in_main_summary
FROM daily_summaries ORDER BY date DESC LIMIT 10;

-- ADOS invite lookup
SELECT member_id, server_nick, global_name
FROM discord_members WHERE member_id = 'DISCORD_USER_ID';

-- Arca Gidan active competitions
SELECT id, title, status FROM competitions WHERE status = 'active';

-- Recent bot logs
SELECT * FROM discord_logs ORDER BY created_at DESC LIMIT 20;
```

---

## Blast Radius

| If this is down... | What breaks | What still works |
|--------------------|------------|-----------------|
| **Supabase** | Bot can't read/write, ADOS invites break, banodoco.ai community empty, Arca Gidan auth + data broken | ArtCompute, static content on all sites |
| **Railway** | Bot goes offline | All websites, existing Supabase data |
| **Discord API** | Bot can't listen or post | All websites (read from Supabase, not Discord) |
| **Claude API** | Summaries stop generating | Bot still archives, reacts, moderates |
| **Solana RPC / CoinGecko** | ArtCompute shows no balance/price | Everything else |

---

## Gotchas

- **ADOS hardcodes Supabase credentials** in `src/pages/Index.tsx` — if keys rotate, update the code and redeploy.
- **brain-of-bndc uses the service role key** — bypasses RLS. Never expose client-side.
- **`write_enabled` flag** — bot checks `server_config.write_enabled` per guild. Silent write failures usually mean this is `FALSE`.
- **Arca Gidan fraud detection** — thresholds in `fraud_detection_config` table. Overly strict settings flag legitimate votes.
- **banodoco-website degrades gracefully** — Supabase down = community section empty, no crash.
