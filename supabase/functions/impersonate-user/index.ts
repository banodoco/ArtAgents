import { createClient } from "npm:@supabase/supabase-js@2";

const JSON_HEADERS = { "Content-Type": "application/json" };

function jsonResponse(status: number, body: Record<string, unknown>) {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers":
          "authorization, content-type, x-client-info, apikey",
      },
    });
  }

  if (req.method !== "POST") {
    return jsonResponse(405, { error: "Method not allowed" });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const supabaseServiceKey = Deno.env.get("SB_SECRET_KEY");

  if (!supabaseUrl || !supabaseServiceKey) {
    return jsonResponse(500, { error: "Missing server configuration" });
  }

  const authHeader = req.headers.get("authorization");
  if (!authHeader) {
    return jsonResponse(401, { error: "Missing authorization header" });
  }

  const accessToken = authHeader.replace(/^Bearer\s+/i, "").trim();
  const supabase = createClient(supabaseUrl, supabaseServiceKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  // Verify caller identity
  const {
    data: { user: caller },
    error: authError,
  } = await supabase.auth.getUser(accessToken);

  if (authError || !caller) {
    return jsonResponse(401, { error: "Invalid token" });
  }

  // Check is_admin flag on members table
  const { data: callerMember } = await supabase
    .from("members")
    .select("is_admin")
    .eq("auth_user_id", caller.id)
    .single();

  if (!callerMember?.is_admin) {
    return jsonResponse(403, { error: "Admin access required" });
  }

  // Parse request
  let body: { target_user_id?: string };
  try {
    body = await req.json();
  } catch {
    return jsonResponse(400, { error: "Invalid JSON body" });
  }

  const targetUserId = body.target_user_id;
  if (!targetUserId) {
    return jsonResponse(400, { error: "target_user_id is required" });
  }

  // Get the target user
  const {
    data: { user: targetUser },
    error: targetError,
  } = await supabase.auth.admin.getUserById(targetUserId);

  if (targetError || !targetUser || !targetUser.email) {
    return jsonResponse(404, { error: "Target user not found or has no email" });
  }

  // Generate a magic link session for the target user
  const { data: linkData, error: linkError } =
    await supabase.auth.admin.generateLink({
      type: "magiclink",
      email: targetUser.email,
    });

  if (linkError || !linkData?.properties) {
    console.error("generateLink failed:", linkError);
    return jsonResponse(500, { error: "Failed to generate session" });
  }

  return jsonResponse(200, {
    access_token: linkData.properties.access_token,
    refresh_token: linkData.properties.refresh_token,
    user: {
      id: targetUser.id,
      email: targetUser.email,
    },
  });
});
