import { createClient } from "npm:@supabase/supabase-js@2";

const HTML_HEADERS = {
  "Content-Type": "text/html; charset=utf-8",
};

const DEFAULT_SITE_ORIGIN = "https://banodoco.ai";
const FALLBACK_IMAGE_PATH = "/2rp-social-card.jpg";

type NodeRow = {
  id: string;
  slug: string;
  name: string;
  short_description: string | null;
  description: string | null;
  catalog_summary: string | null;
};

type MediaRow = {
  media_type: "image" | "video";
  storage_bucket: string;
  storage_path: string;
};

function htmlEscape(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
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

function storagePublicUrl(supabaseUrl: string, media: MediaRow): string {
  const bucket = encodeURIComponent(media.storage_bucket);
  const path = media.storage_path.split("/").map(encodeURIComponent).join("/");
  return `${supabaseUrl}/storage/v1/object/public/${bucket}/${path}`;
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

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SB_SECRET_KEY") ?? Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRoleKey) {
    return new Response("Missing Supabase environment", { status: 500, headers: HTML_HEADERS });
  }

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  const { data, error } = await supabase
    .from("public_agent_node_catalog")
    .select("id, slug, name, short_description, description, catalog_summary")
    .eq("slug", slug)
    .maybeSingle();

  if (error || !data) {
    return new Response("Agent not found", { status: error ? 500 : 404, headers: HTML_HEADERS });
  }

  const node = data as NodeRow;
  const { data: mediaRows } = await supabase
    .from("public_agent_node_media")
    .select("media_type, storage_bucket, storage_path")
    .eq("agent_node_id", node.id)
    .eq("media_type", "image")
    .order("display_order", { ascending: true })
    .order("created_at", { ascending: true })
    .limit(1);

  const media = (mediaRows?.[0] ?? null) as MediaRow | null;
  const canonicalUrl = `${siteOrigin}/art-agents/${encodeURIComponent(node.slug)}`;
  const title = `${node.name} | Art Agents`;
  const summary = stripText(node.catalog_summary || node.short_description || node.description);
  const description = truncate(summary, "Art Agent for Banodoco creative workflows.");
  const imageUrl = media ? storagePublicUrl(supabaseUrl, media) : fallbackImage;

  return new Response(buildHtml({ canonicalUrl, title, description, imageUrl }), { headers: HTML_HEADERS });
});
