import { createClient } from "npm:@supabase/supabase-js@2";

const JSON_HEADERS = { "Content-Type": "application/json" };

function jsonResponse(status: number, body: Record<string, unknown>) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...JSON_HEADERS, "Access-Control-Allow-Origin": "*" },
  });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "authorization, content-type, x-client-info, apikey",
      },
    });
  }

  if (req.method !== "POST") {
    return jsonResponse(405, { error: "Method not allowed" });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceKey = Deno.env.get("SB_SECRET_KEY");
  if (!supabaseUrl || !serviceKey) {
    return jsonResponse(500, { error: "Missing server config" });
  }

  const callerToken = req.headers.get("authorization")?.replace(/^Bearer\s+/i, "").trim();
  if (!callerToken) {
    return jsonResponse(401, { error: "Missing authorization" });
  }

  const supabase = createClient(supabaseUrl, serviceKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  // Verify caller
  const { data: { user: caller }, error: authErr } = await supabase.auth.getUser(callerToken);
  if (authErr || !caller) {
    return jsonResponse(401, { error: "Invalid session" });
  }

  // Check admin via the canonical is_admin() function. Source of truth moved
  // off members.is_admin into the dedicated admins table (migration
  // 20260424000015_simplify_admin_to_own_table); always go through the helper.
  const { data: isAdmin, error: adminErr } = await supabase.rpc("is_admin", {
    check_user_id: caller.id,
  });
  if (adminErr) {
    return jsonResponse(500, { error: "Admin check failed", detail: adminErr.message });
  }
  if (isAdmin !== true) {
    return jsonResponse(403, { error: "Admin only" });
  }

  // Parse target
  let body: { target_user_id?: string };
  try { body = await req.json(); } catch { return jsonResponse(400, { error: "Invalid body" }); }
  if (!body.target_user_id) {
    return jsonResponse(400, { error: "target_user_id required" });
  }

  // Get target user
  const { data: { user: target }, error: targetErr } =
    await supabase.auth.admin.getUserById(body.target_user_id);
  if (targetErr || !target?.email) {
    return jsonResponse(404, { error: "User not found" });
  }

  // Generate link then exchange hashed_token for a real session
  const { data: link, error: linkErr } = await supabase.auth.admin.generateLink({
    type: "magiclink",
    email: target.email,
  });

  if (linkErr || !link?.properties?.hashed_token) {
    return jsonResponse(500, { error: "Link generation failed", detail: linkErr?.message });
  }

  const { data: otpData, error: otpErr } = await supabase.auth.verifyOtp({
    token_hash: link.properties.hashed_token,
    type: "magiclink",
  });

  if (otpErr || !otpData?.session) {
    return jsonResponse(500, { error: "Session creation failed", detail: otpErr?.message });
  }

  return jsonResponse(200, {
    access_token: otpData.session.access_token,
    refresh_token: otpData.session.refresh_token,
  });
});
