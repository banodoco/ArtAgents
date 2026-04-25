import { createClient } from 'npm:@supabase/supabase-js@2';

const JSON_HEADERS = { 'Content-Type': 'application/json' };

function jsonResponse(status: number, body: Record<string, unknown>) {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

function getServiceRoleKey() {
  return Deno.env.get('SB_SECRET_KEY') ?? Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? null;
}

interface DiscordThread {
  id: string;
  name: string;
  type: number;
  parent_id: string | null;
  guild_id?: string;
}

async function discordGet(path: string, token: string) {
  const res = await fetch(`https://discord.com/api/v10${path}`, {
    headers: { Authorization: `Bot ${token}` },
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${path}: ${(await res.text()).slice(0, 200)}`);
  }
  return res.json();
}

async function listThreadsForParent(parentId: string, guildId: string, token: string) {
  const threads: DiscordThread[] = [];
  const active = await discordGet(`/guilds/${guildId}/threads/active`, token);
  for (const t of active.threads ?? []) {
    if (t.parent_id === parentId) threads.push(t);
  }
  let before: string | undefined;
  for (let page = 0; page < 10; page += 1) {
    const q = before ? `?limit=100&before=${encodeURIComponent(before)}` : `?limit=100`;
    const arch = await discordGet(`/channels/${parentId}/threads/archived/public${q}`, token);
    const page_threads = arch.threads ?? [];
    for (const t of page_threads) threads.push(t);
    if (!arch.has_more || page_threads.length === 0) break;
    const last = page_threads[page_threads.length - 1];
    before = last.thread_metadata?.archive_timestamp ?? last.id;
  }
  return threads;
}

Deno.serve(async (req) => {
  if (req.method !== 'POST') return jsonResponse(405, { error: 'Method not allowed' });

  const serviceRoleKey = getServiceRoleKey();
  const authHeader = req.headers.get('authorization');
  if (!serviceRoleKey || !authHeader) return jsonResponse(401, { error: 'Unauthorized' });
  if (authHeader.replace(/^Bearer\s+/i, '').trim() !== serviceRoleKey) {
    return jsonResponse(401, { error: 'Unauthorized' });
  }

  const supabaseUrl = Deno.env.get('SUPABASE_URL');
  const discordToken = Deno.env.get('DISCORD_BOT_TOKEN');
  if (!supabaseUrl || !discordToken) return jsonResponse(500, { error: 'Missing env' });

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  const { data: parents, error: parentErr } = await supabase
    .from('assets')
    .select('discord_channel_id:discord_channel_id::text, discord_guild_id:discord_guild_id::text')
    .eq('source', 'discord_import')
    .not('discord_channel_id', 'is', null)
    .not('discord_guild_id', 'is', null);
  if (parentErr) return jsonResponse(500, { error: parentErr.message });

  const parentMap = new Map<string, string>();
  for (const row of parents ?? []) {
    if (row.discord_channel_id && row.discord_guild_id) {
      parentMap.set(String(row.discord_channel_id), String(row.discord_guild_id));
    }
  }

  let fetched = 0;
  let upserted = 0;
  let errored = 0;
  const errors: string[] = [];
  const parentResults: Record<string, number> = {};

  for (const [parentId, guildId] of parentMap.entries()) {
    try {
      const threads = await listThreadsForParent(parentId, guildId, discordToken);
      parentResults[parentId] = threads.length;
      fetched += threads.length;
      for (const t of threads) {
        const channelType =
          t.type === 11 || t.type === 12 || t.type === 10 ? 'thread' : 'channel';
        const { error: upErr } = await supabase.from('discord_channels').upsert(
          {
            channel_id: t.id,
            channel_name: t.name,
            channel_type: channelType,
            parent_id: t.parent_id,
            guild_id: guildId,
          },
          { onConflict: 'channel_id' },
        );
        if (upErr) {
          errored += 1;
          errors.push(`${t.id}: ${upErr.message}`);
          continue;
        }
        upserted += 1;
      }
    } catch (e) {
      errored += 1;
      errors.push(`parent ${parentId}: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  return jsonResponse(200, {
    parents: parentMap.size,
    parent_results: parentResults,
    fetched,
    upserted,
    errored,
    errors: errors.slice(0, 10),
  });
});
