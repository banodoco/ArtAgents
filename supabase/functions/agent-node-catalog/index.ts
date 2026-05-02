// deno-lint-ignore-file no-explicit-any
import { createClient } from "npm:@supabase/supabase-js@2";

const JSON_HEADERS = {
  "Content-Type": "application/json",
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

type CatalogNodeRow = {
  id: string;
  slug: string;
  name: string;
  node_type: "agent" | "orchestrator";
  short_description: string | null;
  description: string | null;
  repo_url: string;
  expected_manifest_id: string;
  creator_discord_id: string | null;
  creator_display_name: string | null;
  created_at: string;
  updated_at: string;
  is_featured: boolean;
  is_default: boolean;
  is_mandatory: boolean;
  catalog_rank: number;
  catalog_label: string | null;
  catalog_summary: string | null;
};

type InstallTargetRow = {
  id: string;
  agent_node_id: string;
  label: string | null;
  source_type: "git" | "manifest_url" | "archive_url";
  repo_url: string | null;
  manifest_url: string | null;
  archive_url: string | null;
  commit_sha: string | null;
  tag: string | null;
  branch: string | null;
  source_ref: string | null;
  manifest_path: string | null;
  expected_node_id: string;
  install_subdir: string | null;
  created_at: string;
};

type MediaRow = {
  id: string;
  agent_node_id: string;
  media_type: "image" | "video";
  storage_bucket: string;
  storage_path: string;
  mime_type: string;
  file_size_bytes: number;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  alt_text: string | null;
  caption: string | null;
  display_order: number;
  created_at: string;
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

function chosenRef(target: InstallTargetRow): Record<string, string> {
  if (target.commit_sha) return { commit_sha: target.commit_sha };
  if (target.tag) return { tag: target.tag };
  if (target.branch) return { branch: target.branch };
  if (target.source_ref) return { source_ref: target.source_ref };
  return {};
}

function byNodeId<T extends { agent_node_id: string }>(rows: T[]): Map<string, T[]> {
  const grouped = new Map<string, T[]>();
  for (const row of rows) {
    const existing = grouped.get(row.agent_node_id);
    if (existing) existing.push(row);
    else grouped.set(row.agent_node_id, [row]);
  }
  return grouped;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: JSON_HEADERS });
  }
  if (req.method !== "GET") {
    return jsonResponse({ error: "Method not allowed" }, 405);
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceKey = Deno.env.get("SB_SECRET_KEY") ?? Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceKey) {
    return jsonResponse({ error: "Supabase service credentials are not configured" }, 500);
  }

  const supabase = createClient(supabaseUrl, serviceKey);

  const { data: nodes, error: nodeError } = await supabase
    .from("public_agent_node_catalog")
    .select("*")
    .order("catalog_rank", { ascending: true })
    .order("name", { ascending: true });

  if (nodeError) {
    console.error("[agent-node-catalog] nodes failed", nodeError.message);
    return jsonResponse({ error: "Failed to fetch agent node catalog" }, 500);
  }

  const { data: targets, error: targetError } = await supabase
    .from("public_agent_node_install_targets")
    .select("*")
    .order("created_at", { ascending: true });

  if (targetError) {
    console.error("[agent-node-catalog] targets failed", targetError.message);
    return jsonResponse({ error: "Failed to fetch agent node install targets" }, 500);
  }

  const { data: media, error: mediaError } = await supabase
    .from("public_agent_node_media")
    .select("*")
    .order("display_order", { ascending: true })
    .order("created_at", { ascending: true });

  if (mediaError) {
    console.error("[agent-node-catalog] media failed", mediaError.message);
    return jsonResponse({ error: "Failed to fetch agent node media" }, 500);
  }

  const targetsByNode = byNodeId((targets ?? []) as InstallTargetRow[]);
  const mediaByNode = byNodeId((media ?? []) as MediaRow[]);
  const payloadNodes = ((nodes ?? []) as CatalogNodeRow[]).map((node) => ({
    id: node.id,
    slug: node.slug,
    name: node.name,
    node_type: node.node_type ?? "agent",
    short_description: node.short_description,
    description: node.description,
    repo_url: node.repo_url,
    expected_manifest_id: node.expected_manifest_id,
    creator: {
      discord_id: node.creator_discord_id,
      display_name: node.creator_display_name,
    },
    catalog: {
      featured: node.is_featured,
      default: node.is_default,
      mandatory: node.is_mandatory,
      rank: node.catalog_rank,
      label: node.catalog_label,
      summary: node.catalog_summary,
    },
    install_targets: (targetsByNode.get(node.id) ?? []).map((target) => ({
      id: target.id,
      label: target.label,
      source_type: target.source_type,
      repo_url: target.repo_url,
      manifest_url: target.manifest_url,
      archive_url: target.archive_url,
      manifest_path: target.manifest_path,
      expected_node_id: target.expected_node_id,
      install_subdir: target.install_subdir,
      ref: chosenRef(target),
    })),
    media: (mediaByNode.get(node.id) ?? []).map((item) => ({
      id: item.id,
      type: item.media_type,
      bucket: item.storage_bucket,
      path: item.storage_path,
      mime_type: item.mime_type,
      file_size_bytes: item.file_size_bytes,
      width: item.width,
      height: item.height,
      duration_seconds: item.duration_seconds,
      alt_text: item.alt_text,
      caption: item.caption,
    })),
    created_at: node.created_at,
    updated_at: node.updated_at,
  }));

  return jsonResponse({
    nodes: payloadNodes,
    default_node_ids: payloadNodes.filter((node) => node.catalog.default).map((node) => node.expected_manifest_id),
    mandatory_node_ids: payloadNodes.filter((node) => node.catalog.mandatory).map((node) => node.expected_manifest_id),
  });
});
