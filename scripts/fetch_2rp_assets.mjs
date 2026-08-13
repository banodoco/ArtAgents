import { createClient } from '@supabase/supabase-js';
import { writeFileSync, mkdirSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const url = process.env.VITE_SUPABASE_URL;
const key = process.env.VITE_SUPABASE_ANON_KEY;

if (!url || !key) {
  console.error('Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY env vars');
  process.exit(1);
}

const supabase = createClient(url, key);
const outDir = join(__dirname, '..', 'projects', '2rp-launch-assets');
mkdirSync(outDir, { recursive: true });

async function fetchHeroArtists() {
  const usernames = ['VisualFrisson', 'fabdream', 'emmacatnip'];
  const memberFilter = usernames.map(u => `username.ilike.${u}`).join(',');
  const { data: members, error: memberError } = await supabase
    .from('members')
    .select('member_id:member_id::text, username, global_name, avatar_url')
    .or(memberFilter);
  if (memberError) throw memberError;

  const memberMap = new Map();
  for (const m of members || []) {
    if (m.username) memberMap.set(m.username.toLowerCase(), m);
  }

  const pieces = [];
  for (const username of usernames) {
    const member = memberMap.get(username.toLowerCase());
    if (!member) continue;
    const { data, error } = await supabase
      .from('media')
      .select('id, type, title, description, cloudflare_thumbnail_url, cloudflare_playback_hls_url, backup_thumbnail_url, admin_status, created_at, member_id:member_id::text')
      .eq('member_id', member.member_id)
      .eq('type', 'video')
      .eq('featured_on_2rf', true)
      .order('created_at', { ascending: false })
      .limit(1);
    if (error) throw error;
    if (data && data[0]) {
      pieces.push({ ...data[0], creator_username: member.username, creator_display_name: member.global_name, creator_avatar_url: member.avatar_url });
    }
  }
  return pieces;
}

async function fetchArtGallery() {
  const { data, error } = await supabase
    .from('media')
    .select('id, type, title, description, cloudflare_thumbnail_url, cloudflare_playback_hls_url, backup_thumbnail_url, admin_status, created_at, member_id:member_id::text, featured_on_2rf')
    .eq('source', 'art')
    .eq('featured_on_2rf', true)
    .order('created_at', { ascending: false })
    .limit(50);
  if (error) throw error;
  return data || [];
}

async function fetchAgentNodes() {
  const response = await fetch(`${url}/functions/v1/agent-node-catalog`, {
    headers: { Accept: 'application/json', apikey: key, Authorization: `Bearer ${key}` },
  });
  if (!response.ok) throw new Error(`agent-node-catalog failed: ${response.status}`);
  return await response.json();
}

async function fetchResources() {
  const { data, error } = await supabase
    .from('assets')
    .select(`
      id, slug, type, name, description, source, is_hidden, admin_status, creator,
      member_id:member_id::text,
      lora_type, lora_base_model, model_variant,
      lora_link, download_link, primary_media_id, created_at,
      media:primary_media_id (
        id, type, cloudflare_thumbnail_url, backup_thumbnail_url,
        cloudflare_playback_hls_url, placeholder_image, metadata
      )
    `)
    .eq('is_hidden', false)
    .eq('status', 'published')
    .in('admin_status', ['Curated', 'Listed'])
    .order('created_at', { ascending: false })
    .limit(100);
  if (error) throw error;
  return data || [];
}

async function fetchPosts() {
  const { data, error } = await supabase
    .from('posts')
    .select('id, title, slug, status, admin_status, render_mode, created_at, updated_at, published_at, member_id:member_id::text, cover_media_id')
    .eq('status', 'published')
    .or('admin_status.is.null,admin_status.neq.Hidden')
    .order('published_at', { ascending: false })
    .order('updated_at', { ascending: false })
    .limit(20);
  if (error) throw error;

  const coverIds = [...new Set((data || []).map(r => r.cover_media_id).filter(Boolean))];
  let mediaMap = new Map();
  if (coverIds.length > 0) {
    const { data: mediaData, error: mediaError } = await supabase
      .from('media')
      .select('id, type, cloudflare_thumbnail_url, cloudflare_playback_hls_url, backup_thumbnail_url')
      .in('id', coverIds);
    if (mediaError) throw mediaError;
    for (const m of mediaData || []) mediaMap.set(m.id, m);
  }

  const memberIds = [...new Set((data || []).map(r => r.member_id).filter(Boolean))];
  let memberMap = new Map();
  if (memberIds.length > 0) {
    const { data: memberData, error: memberError } = await supabase
      .from('members')
      .select('member_id:member_id::text, username, global_name, avatar_url')
      .in('member_id', memberIds);
    if (memberError) throw memberError;
    for (const m of memberData || []) memberMap.set(m.member_id, m);
  }

  return (data || []).map(p => ({
    ...p,
    cover: mediaMap.get(p.cover_media_id) || null,
    creator: memberMap.get(p.member_id) || null,
  }));
}

async function fetchCommunityNews() {
  const { data: dateRows, error: dateError } = await supabase
    .from('daily_summaries')
    .select('date')
    .eq('included_in_main_summary', true)
    .eq('dev_mode', false)
    .order('date', { ascending: false })
    .limit(30);
  if (dateError) throw dateError;
  const uniqueDates = [...new Set((dateRows || []).map(r => r.date))];
  if (uniqueDates.length === 0) return [];

  const { data, error } = await supabase
    .from('daily_summaries')
    .select('full_summary, date, channel_id, discord_channels(channel_name)')
    .eq('included_in_main_summary', true)
    .eq('dev_mode', false)
    .in('date', uniqueDates.slice(0, 7))
    .order('date', { ascending: false });
  if (error) throw error;

  const IMAGE_EXTENSIONS = /\.(jpg|jpeg|jfif|png|gif|webp|avif|bmp|tiff?|svg|heic|heif)(\?|$)/i;
  const VIDEO_EXTENSIONS = /\.(mp4|webm|mov|avi|mkv|m4v|ogv|3gp|ts|mts|m2ts)(\?|$)/i;
  const isValidMediaUrl = (media) => {
    if (!media.url) return false;
    const url = media.url.toLowerCase();
    if (media.type === 'video') return VIDEO_EXTENSIONS.test(url);
    if (media.type === 'image') return IMAGE_EXTENSIONS.test(url);
    return IMAGE_EXTENSIONS.test(url) || VIDEO_EXTENSIONS.test(url);
  };
  const extractMediaUrls = (rawTopic) => {
    const urls = [];
    if (rawTopic.mainMediaUrls) urls.push(...rawTopic.mainMediaUrls);
    if (rawTopic.subTopics) {
      for (const st of rawTopic.subTopics) {
        if (st.included_in_main && st.subTopicMediaUrls) {
          for (const group of st.subTopicMediaUrls) {
            if (Array.isArray(group)) urls.push(...group);
          }
        }
      }
    }
    return urls.filter(isValidMediaUrl);
  };

  const topics = [];
  for (const summary of data || []) {
    try {
      const rawTopics = JSON.parse(summary.full_summary);
      const included = rawTopics.filter(t => t.included_in_main === true);
      const channelName = Array.isArray(summary.discord_channels)
        ? summary.discord_channels[0]?.channel_name
        : summary.discord_channels?.channel_name;
      for (const rawTopic of included) {
        topics.push({
          date: summary.date,
          channel_id: summary.channel_id,
          channel_name: channelName || 'community',
          title: rawTopic.title,
          main_text: rawTopic.mainText,
          mediaUrls: extractMediaUrls(rawTopic),
        });
      }
    } catch (e) {
      console.error('parse error', e);
    }
  }
  return topics;
}

async function main() {
  console.log('Fetching 2RP assets...');
  const results = {
    fetched_at: new Date().toISOString(),
    page_url: 'https://banodoco.ai/2rp',
    sections: {
      hero: { title: 'Hero Artist Cycler', source: 'media table, featured_on_2rf videos by VisualFrisson, fabdream, emmacatnip' },
      art: { title: 'Art', source: 'media table, source=art, featured_on_2rf=true' },
      agents: { title: 'Art Agents', source: 'Supabase function agent-node-catalog' },
      resources: { title: 'Resources', source: 'assets table, status=published, admin_status in [Curated, Listed]' },
      briefing: { title: 'Briefing Videos', source: 'Hardcoded YouTube embeds' },
      community_news: { title: 'Community News', source: 'daily_summaries table' },
      posts: { title: 'Posts', source: 'posts table, status=published' },
      community_montage: { title: 'Community Montage', source: 'Local /assorted_propaganda/*.webp frames' },
    },
    hero_artists: await fetchHeroArtists(),
    art_gallery: await fetchArtGallery(),
    agent_nodes: await fetchAgentNodes(),
    resources: await fetchResources(),
    posts: await fetchPosts(),
    community_news: await fetchCommunityNews(),
  };

  const outPath = join(outDir, '2rp_assets_raw.json');
  writeFileSync(outPath, JSON.stringify(results, null, 2));
  console.log(`Wrote ${outPath}`);
  console.log('Counts:');
  console.log(`  hero_artists: ${results.hero_artists.length}`);
  console.log(`  art_gallery: ${results.art_gallery.length}`);
  console.log(`  agent_nodes: ${results.agent_nodes.nodes?.length || 0}`);
  console.log(`  resources: ${results.resources.length}`);
  console.log(`  posts: ${results.posts.length}`);
  console.log(`  community_news: ${results.community_news.length}`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
