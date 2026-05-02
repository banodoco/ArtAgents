import { createClient } from "npm:@supabase/supabase-js@2";

const HTML_HEADERS = {
  "Content-Type": "text/html; charset=utf-8",
};

const DEFAULT_SITE_ORIGIN = "https://banodoco.ai";
const FALLBACK_IMAGE_PATH = "/2rp-social-card.jpg";
const BASE62_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";

type MediaRow = {
  id: string;
  title: string | null;
  description: string | null;
  cloudflare_thumbnail_url: string | null;
  backup_thumbnail_url: string | null;
  member_id: string | null;
};

function htmlEscape(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function decodeUuidBase62(token: string): string | null {
  if (!token) return null;

  let value = 0n;
  for (const char of token) {
    const idx = BASE62_ALPHABET.indexOf(char);
    if (idx < 0) return null;
    value = value * 62n + BigInt(idx);
  }

  const hex = value.toString(16).padStart(32, "0");
  if (hex.length !== 32) return null;

  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20, 32),
  ].join("-");
}

function slugToId(slug: string): string | null {
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(slug)) {
    return slug;
  }

  const token = slug.includes("--") ? slug.split("--").pop() ?? "" : slug;
  return decodeUuidBase62(token);
}

function slugify(value: string | null | undefined): string {
  const base = (value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/[\s-]+/g, "-")
    .replace(/^-+|-+$/g, "");

  return base || "item";
}

function encodeUuidBase62(uuid: string): string | null {
  const hex = uuid.replace(/-/g, "").toLowerCase();
  if (!/^[0-9a-f]{32}$/.test(hex)) return null;

  let value = BigInt(`0x${hex}`);
  if (value === 0n) return "0";

  let encoded = "";
  while (value > 0) {
    const mod = Number(value % 62n);
    encoded = BASE62_ALPHABET[mod] + encoded;
    value /= 62n;
  }
  return encoded;
}

function buildEntitySlug(label: string | null | undefined, id: string): string {
  const token = encodeUuidBase62(id);
  if (!token) return slugify(label);
  return `${slugify(label)}--${token}`;
}

function stripText(value: string | null | undefined): string {
  return (value ?? "").replace(/\s+/g, " ").trim();
}

function truncate(value: string, fallback: string): string {
  const text = value || fallback;
  return text.length > 200 ? `${text.slice(0, 197)}...` : text;
}

function resolveSiteOrigin(req: Request): string {
  const forwardedHost = req.headers.get("x-forwarded-host");
  const forwardedProto = req.headers.get("x-forwarded-proto") ?? "https";
  return forwardedHost ? `${forwardedProto}://${forwardedHost}` : DEFAULT_SITE_ORIGIN;
}

function buildHtml(params: {
  canonicalUrl: string;
  title: string;
  description: string;
  imageUrl: string;
}) {
  const title = htmlEscape(params.title);
  const description = htmlEscape(params.description);
  const canonicalUrl = htmlEscape(params.canonicalUrl);
  const imageUrl = htmlEscape(params.imageUrl);

  return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>${title}</title>
    <meta name="description" content="${description}" />
    <meta property="og:title" content="${title}" />
    <meta property="og:description" content="${description}" />
    <meta property="og:image" content="${imageUrl}" />
    <meta property="og:url" content="${canonicalUrl}" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="${title}" />
    <meta name="twitter:description" content="${description}" />
    <meta name="twitter:image" content="${imageUrl}" />
    <link rel="canonical" href="${canonicalUrl}" />
    <meta http-equiv="refresh" content="0; url=${canonicalUrl}" />
  </head>
  <body>
    <p>Redirecting to <a href="${canonicalUrl}">${canonicalUrl}</a>...</p>
  </body>
</html>`;
}

Deno.serve(async (req) => {
  if (req.method !== "GET") {
    return new Response("Method not allowed", { status: 405, headers: HTML_HEADERS });
  }

  const requestUrl = new URL(req.url);
  const slug = requestUrl.searchParams.get("slug")?.trim();
  const siteOrigin = resolveSiteOrigin(req);
  const fallbackImage = `${siteOrigin}${FALLBACK_IMAGE_PATH}`;

  if (!slug) {
    return new Response("Missing slug", { status: 400, headers: HTML_HEADERS });
  }

  const artId = slugToId(slug);
  if (!artId) {
    return new Response("Invalid art slug", { status: 400, headers: HTML_HEADERS });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SB_SECRET_KEY") ?? Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRoleKey) {
    return new Response("Missing Supabase environment", { status: 500, headers: HTML_HEADERS });
  }

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  const { data, error } = await supabase
    .from("media")
    .select("id, title, description, cloudflare_thumbnail_url, backup_thumbnail_url, member_id:member_id::text")
    .eq("id", artId)
    .maybeSingle();

  if (error || !data) {
    return new Response("Art not found", { status: error ? 500 : 404, headers: HTML_HEADERS });
  }

  const media = data as MediaRow;
  let creatorName = "";
  let username = "";
  if (media.member_id) {
    const { data: member } = await supabase
      .from("members")
      .select("global_name, username")
      .eq("member_id", media.member_id)
      .maybeSingle();

    creatorName = member?.global_name?.trim() || member?.username?.trim() || "";
    username = member?.username?.trim() || "";
  }

  const label = media.description || media.title || null;
  const canonicalPath = username
    ? `/${encodeURIComponent(username)}/art/${buildEntitySlug(label, media.id)}`
    : `/art/${buildEntitySlug(label, media.id)}`;
  const canonicalUrl = `${siteOrigin}${canonicalPath}`;
  const title = media.title || media.description || (creatorName ? `Art by ${creatorName}` : "Banodoco Art");
  const description = truncate(stripText(media.description), creatorName ? `Artwork by ${creatorName}` : "Artwork on Banodoco.");
  const imageUrl = media.backup_thumbnail_url ?? media.cloudflare_thumbnail_url ?? fallbackImage;

  return new Response(buildHtml({ canonicalUrl, title, description, imageUrl }), { headers: HTML_HEADERS });
});
