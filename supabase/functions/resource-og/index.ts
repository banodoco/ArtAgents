import { createClient } from "npm:@supabase/supabase-js@2";

const HTML_HEADERS = {
  "Content-Type": "text/html; charset=utf-8",
};

const FALLBACK_IMAGE_PATH = "/2rp-social-card.jpg";
const DEFAULT_SITE_ORIGIN = "https://banodoco.ai";

interface AssetRow {
  slug: string;
  name: string;
  description: string | null;
  member_id: string | null;
  primary_media: {
    url: string | null;
    cloudflare_thumbnail_url: string | null;
    backup_thumbnail_url: string | null;
  } | {
    url: string | null;
    cloudflare_thumbnail_url: string | null;
    backup_thumbnail_url: string | null;
  }[] | null;
}

function htmlEscape(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function unwrapJoined<T>(value: T | T[] | null): T | null {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  return value;
}

function stripMarkdown(markdown: string | null): string {
  if (!markdown) {
    return "";
  }

  return markdown
    .replace(/!\[[^\]]*]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/`{1,3}[^`]*`{1,3}/g, " ")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^>\s?/gm, "")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/\*\*|__|\*|_|~~/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function truncateDescription(markdown: string | null): string {
  const stripped = stripMarkdown(markdown);
  if (!stripped) {
    return "Discover art, resources, and creative tooling on Banodoco.";
  }

  return stripped.length > 200 ? `${stripped.slice(0, 197)}...` : stripped;
}

function resolveSiteOrigin(req: Request): string {
  const forwardedHost = req.headers.get("x-forwarded-host");
  const forwardedProto = req.headers.get("x-forwarded-proto") ?? "https";

  if (forwardedHost) {
    return `${forwardedProto}://${forwardedHost}`;
  }

  return DEFAULT_SITE_ORIGIN;
}

function buildHtml(params: {
  canonicalUrl: string;
  redirectUrl: string;
  title: string;
  description: string;
  imageUrl: string;
}) {
  const title = htmlEscape(params.title);
  const description = htmlEscape(params.description);
  const canonicalUrl = htmlEscape(params.canonicalUrl);
  const imageUrl = htmlEscape(params.imageUrl);
  const redirectUrl = htmlEscape(params.redirectUrl);

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
    <meta http-equiv="refresh" content="0; url=${redirectUrl}" />
  </head>
  <body>
    <p>Redirecting to <a href="${redirectUrl}">${redirectUrl}</a>...</p>
  </body>
</html>`;
}

Deno.serve(async (req) => {
  if (req.method !== "GET") {
    return new Response("Method not allowed", { status: 405, headers: HTML_HEADERS });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SB_SECRET_KEY") ?? Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

  if (!supabaseUrl || !serviceRoleKey) {
    return new Response("Missing Supabase environment", { status: 500, headers: HTML_HEADERS });
  }

  const requestUrl = new URL(req.url);
  const slug = requestUrl.searchParams.get("slug")?.trim();

  if (!slug) {
    return new Response("Missing slug", { status: 400, headers: HTML_HEADERS });
  }

  const siteOrigin = resolveSiteOrigin(req);
  const redirectUrl = `${siteOrigin}/resources/${encodeURIComponent(slug)}`;
  const fallbackImage = `${siteOrigin}${FALLBACK_IMAGE_PATH}`;

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });

  const { data, error } = await supabase
    .from("assets")
    .select(
      "slug, name, description, member_id:member_id::text, primary_media:primary_media_id(url, cloudflare_thumbnail_url, backup_thumbnail_url)",
    )
    .eq("slug", slug)
    .eq("status", "published")
    .maybeSingle();

  if (error || !data) {
    const html = buildHtml({
      canonicalUrl: redirectUrl,
      redirectUrl,
      title: "Banodoco Resource",
      description: "Discover art, resources, and creative tooling on Banodoco.",
      imageUrl: fallbackImage,
    });

    return new Response(html, {
      status: error ? 500 : 404,
      headers: HTML_HEADERS,
    });
  }

  const asset = data as AssetRow;
  const primaryMedia = unwrapJoined(asset.primary_media);
  const imageUrl =
    primaryMedia?.cloudflare_thumbnail_url
    ?? primaryMedia?.backup_thumbnail_url
    ?? fallbackImage;

  let creatorName = "";
  if (asset.member_id) {
    const { data: member } = await supabase
      .from("members")
      .select("global_name, username")
      .eq("member_id", asset.member_id)
      .maybeSingle();

    creatorName = member?.global_name?.trim() || member?.username?.trim() || "";
  }

  const title = creatorName ? `${asset.name} by ${creatorName}` : asset.name;
  const description = truncateDescription(asset.description);
  const canonicalUrl = `${siteOrigin}/resources/${asset.slug}`;
  const html = buildHtml({
    canonicalUrl,
    redirectUrl: canonicalUrl,
    title,
    description,
    imageUrl,
  });

  return new Response(html, { status: 200, headers: HTML_HEADERS });
});
