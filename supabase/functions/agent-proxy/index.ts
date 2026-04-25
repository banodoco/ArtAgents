// Vibe Mode agent-proxy Edge Function.
//
// POST /functions/v1/agent-proxy — bearer-authed SSE streaming bridge
// between the Vibe editor and the Anthropic Messages API.
//
// Implementation honours four hard-rails from the Vibe Mode plan:
//   (a) SSE event order: text | tool_call | tool_result | safety_warning
//       | usage | done | refusal | error (never emit any other order).
//   (b) Check + charge metering: `vibe_usage_check` before Anthropic;
//       `vibe_usage_charge` exactly once after settle — INCLUDING on
//       `stop_reason === 'refusal'` (FLAG-002, success criterion #18).
//   (c) Exactly TWO Anthropic cache_control breakpoints — see
//       `./anthropic.ts`.
//   (d) Advisory safety scan runs on the post-batch tree and is never
//       a hard block.

import { createClient, type SupabaseClient } from 'npm:@supabase/supabase-js@2';
import { runAgentTurn, estimateUsdCost } from './anthropic.ts';
import { applyToolBatch } from './tools.ts';
import { scanTree, describeFinding } from './safety.ts';
import { buildSystemPromptForTurn } from './systemPrompt.ts';
import type {
  AgentProxyRequestBody,
  ToolUseCall,
  VibeModel,
  VirtualFileTree,
} from './types.ts';

const ALLOWED_MODELS: VibeModel[] = [
  'claude-sonnet-4-6',
  'claude-opus-4-7',
  'claude-haiku-4-5',
];

const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MAX_IMAGE_EDGE = 1920;

const JSON_HEADERS = { 'Content-Type': 'application/json' };
const SSE_HEADERS = {
  'Content-Type': 'text/event-stream; charset=utf-8',
  'Cache-Control': 'no-store, no-transform',
  Connection: 'keep-alive',
  'X-Accel-Buffering': 'no',
};

const jsonResponse = (status: number, body: Record<string, unknown>) =>
  new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, content-type, x-client-info, apikey',
};

const approxDataUrlBytes = (dataUrl: string): number => {
  const idx = dataUrl.indexOf(',');
  if (idx === -1) return dataUrl.length;
  const b64 = dataUrl.slice(idx + 1);
  return Math.floor((b64.length * 3) / 4);
};

const validateImagesServerSide = (
  images?: Array<{ mime: string; dataUrl: string; width: number; height: number }>,
): string | null => {
  if (!images) return null;
  for (let i = 0; i < images.length; i++) {
    const img = images[i];
    if (typeof img.width !== 'number' || typeof img.height !== 'number') {
      return `image[${i}]: width and height are required`;
    }
    if (Math.max(img.width, img.height) > MAX_IMAGE_EDGE) {
      return `image[${i}]: longest edge ${Math.max(img.width, img.height)}px exceeds ${MAX_IMAGE_EDGE}px`;
    }
    if (approxDataUrlBytes(img.dataUrl) > MAX_IMAGE_BYTES) {
      return `image[${i}]: payload exceeds ${MAX_IMAGE_BYTES} bytes`;
    }
  }
  return null;
};

const parseBody = async (req: Request): Promise<AgentProxyRequestBody | { _err: string }> => {
  try {
    const body = await req.json();
    if (typeof body !== 'object' || body === null) return { _err: 'body must be an object' };
    const b = body as Record<string, unknown>;
    if (typeof b.postDraftId !== 'string') return { _err: 'postDraftId is required' };
    if (typeof b.model !== 'string' || !ALLOWED_MODELS.includes(b.model as VibeModel)) {
      return { _err: `model must be one of ${ALLOWED_MODELS.join(', ')}` };
    }
    if (typeof b.tree !== 'object' || b.tree === null) return { _err: 'tree is required' };
    if (!Array.isArray(b.chatHistory)) return { _err: 'chatHistory must be an array' };
    if (typeof b.userTurn !== 'object' || b.userTurn === null) return { _err: 'userTurn is required' };
    const userTurn = b.userTurn as Record<string, unknown>;
    if (typeof userTurn.text !== 'string') return { _err: 'userTurn.text is required' };
    return body as AgentProxyRequestBody;
  } catch {
    return { _err: 'invalid JSON body' };
  }
};

// SSE frame writer — `event:` + `data:` + blank line. We emit ONLY the
// event names from the approved order; any caller writing through this
// writer therefore cannot violate the ordering contract on its own.
class SseWriter {
  private readonly controller: ReadableStreamDefaultController<Uint8Array>;
  private readonly encoder = new TextEncoder();
  private closed = false;

  constructor(controller: ReadableStreamDefaultController<Uint8Array>) {
    this.controller = controller;
  }

  write(event: string, data: unknown): void {
    if (this.closed) return;
    const json = typeof data === 'string' ? data : JSON.stringify(data);
    this.controller.enqueue(
      this.encoder.encode(`event: ${event}\ndata: ${json}\n\n`),
    );
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    try {
      this.controller.close();
    } catch {
      // controller may already be closed if the client aborted.
    }
  }
}

const chargeUsage = async (
  supabase: SupabaseClient,
  userId: string,
  inputTokens: number,
  outputTokens: number,
): Promise<{ dailyTokens: number } | null> => {
  const { data, error } = await supabase.rpc('vibe_usage_charge', {
    p_user_id: userId,
    p_input: inputTokens,
    p_output: outputTokens,
  });
  if (error) {
    console.error('vibe_usage_charge failed', error);
    return null;
  }
  const row = Array.isArray(data) ? data[0] : data;
  if (row && typeof row === 'object' && 'daily_tokens' in row) {
    const v = (row as Record<string, unknown>).daily_tokens;
    if (typeof v === 'number' || typeof v === 'bigint' || typeof v === 'string') {
      return { dailyTokens: Number(v) };
    }
  }
  return null;
};

const runPreflight = async (
  supabase: SupabaseClient,
  userId: string,
): Promise<
  | { allowed: true; tokensRemaining: number }
  | { allowed: false; reason: 'vibe_rate_limited' | 'vibe_daily_budget_exceeded'; tokensRemaining: number }
> => {
  const { data, error } = await supabase.rpc('vibe_usage_check', { p_user_id: userId });
  if (error) {
    console.error('vibe_usage_check failed', error);
    // Fail-closed on RPC error so a broken meter cannot drain budget.
    return { allowed: false, reason: 'vibe_daily_budget_exceeded', tokensRemaining: 0 };
  }
  const row = Array.isArray(data) ? data[0] : data;
  const tokensRemaining = row && 'tokens_remaining' in (row as Record<string, unknown>)
    ? Number((row as Record<string, unknown>).tokens_remaining ?? 0)
    : 0;

  // Also read the current minute-window row to enforce the 30 req/min
  // rate limit. We do this server-side here rather than in the RPC so
  // the migration stays byte-identical to doc §Step 3.
  const rateLimit = Number(Deno.env.get('VIBE_RATE_LIMIT_REQ_PER_MIN') ?? '30');
  const { data: usageRow, error: usageErr } = await supabase
    .from('vibe_usage')
    .select('req_this_minute, minute_window_started_at')
    .eq('user_id', userId)
    .eq('day', new Date().toISOString().slice(0, 10))
    .maybeSingle();
  if (!usageErr && usageRow) {
    const windowStarted = new Date(usageRow.minute_window_started_at as string).getTime();
    const withinWindow = Date.now() - windowStarted < 60_000;
    if (withinWindow && Number(usageRow.req_this_minute ?? 0) >= rateLimit) {
      return { allowed: false, reason: 'vibe_rate_limited', tokensRemaining };
    }
  }

  if (tokensRemaining <= 0) {
    return { allowed: false, reason: 'vibe_daily_budget_exceeded', tokensRemaining };
  }
  return { allowed: true, tokensRemaining };
};

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }
  if (req.method !== 'POST') {
    return jsonResponse(405, { error: { code: 'method_not_allowed', message: 'POST only' } });
  }

  const authHeader = req.headers.get('authorization');
  if (!authHeader) {
    return jsonResponse(401, { error: { code: 'vibe_auth_required', message: 'Missing authorization header' } });
  }

  const supabaseUrl = Deno.env.get('SUPABASE_URL');
  const serviceKey = Deno.env.get('SB_SECRET_KEY');
  const anthropicKey = Deno.env.get('ANTHROPIC_API_KEY');
  if (!supabaseUrl || !serviceKey || !anthropicKey) {
    return jsonResponse(500, { error: { code: 'vibe_misconfigured', message: 'Missing required environment variables' } });
  }

  const accessToken = authHeader.replace(/^Bearer\s+/i, '').trim();
  if (!accessToken) {
    return jsonResponse(401, { error: { code: 'vibe_auth_required', message: 'Invalid authorization header' } });
  }

  const supabase = createClient(supabaseUrl, serviceKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  const { data: { user }, error: authError } = await supabase.auth.getUser(accessToken);
  if (authError || !user) {
    return jsonResponse(401, { error: { code: 'vibe_auth_required', message: 'Invalid token' } });
  }

  const body = await parseBody(req);
  if ('_err' in body) {
    return jsonResponse(400, { error: { code: 'vibe_bad_request', message: body._err } });
  }

  const imageErr = validateImagesServerSide(body.userTurn.images);
  if (imageErr) {
    return jsonResponse(413, { error: { code: 'vibe_image_too_large', message: imageErr } });
  }

  const preflight = await runPreflight(supabase, user.id);
  if (!preflight.allowed) {
    return jsonResponse(429, {
      error: {
        code: preflight.reason,
        message:
          preflight.reason === 'vibe_rate_limited'
            ? 'Rate limit exceeded for this minute.'
            : 'Daily token budget exceeded.',
        tokensRemaining: preflight.tokensRemaining,
      },
    });
  }

  const dailyBudget = Number(Deno.env.get('VIBE_DAILY_TOKEN_BUDGET') ?? '500000');
  const workingTree: VirtualFileTree = JSON.parse(JSON.stringify(body.tree));

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const writer = new SseWriter(controller);
      const pendingToolCalls: ToolUseCall[] = [];
      let charged = false;
      let refusalText: string | null = null;

      // Always try to charge exactly once (success OR refusal), per FLAG-002.
      const settleCharge = async (
        inputTokens: number,
        outputTokens: number,
        model: VibeModel,
        sessionTokensUsed: number,
      ) => {
        if (charged) return;
        charged = true;
        const chargeResult = await chargeUsage(supabase, user.id, inputTokens, outputTokens);
        const totalTokens = inputTokens + outputTokens;
        writer.write('usage', {
          model,
          inputTokens,
          outputTokens,
          totalTokens,
          estimatedUsd: estimateUsdCost(model, {
            input_tokens: inputTokens,
            output_tokens: outputTokens,
          }),
          sessionTokensUsed: sessionTokensUsed + totalTokens,
          dailyTokensUsed: chargeResult?.dailyTokens ?? 0,
          dailyTokensBudget: dailyBudget,
        });
      };

      try {
        const isFirstTurn = body.chatHistory.length === 0;
        const effectiveSystemPrompt = buildSystemPromptForTurn(
          isFirstTurn,
          body.templateContinuation ?? null,
        );
        await runAgentTurn({
          apiKey: anthropicKey,
          model: body.model,
          systemPrompt: effectiveSystemPrompt,
          tree: workingTree,
          chatHistory: body.chatHistory,
          userTurn: body.userTurn,
          signal: req.signal,
          callbacks: {
            onText(delta: string) {
              writer.write('text', { delta });
            },
            onToolUse(call: ToolUseCall) {
              pendingToolCalls.push(call);
              const p = (call.input as { path?: unknown }).path;
              writer.write('tool_call', {
                tool: call.name,
                path: typeof p === 'string' ? p : '',
              });
            },
            onStop({ stop_reason, usage }) {
              const inputTokens = usage?.input_tokens ?? 0;
              const outputTokens = usage?.output_tokens ?? 0;

              if (stop_reason === 'refusal') {
                refusalText = 'The model declined this turn.';
                // No tool calls applied on refusal. FLAG-002: still charge.
                settleCharge(inputTokens, outputTokens, body.model, 0).catch((e) =>
                  console.error('charge (refusal path) failed', e),
                );
                return;
              }

              // Apply buffered tool batch AFTER message_stop.
              const results = applyToolBatch(workingTree, pendingToolCalls);
              for (const r of results) {
                writer.write('tool_result', {
                  tool: r.tool,
                  path: r.path,
                  ok: r.ok,
                  summary: r.summary,
                  error: r.error,
                });
              }

              // Advisory safety scan over the post-batch tree.
              const findings = scanTree(workingTree);
              for (const f of findings) {
                writer.write('safety_warning', {
                  rule: f.rule,
                  path: f.path,
                  text: describeFinding(f),
                });
              }

              settleCharge(inputTokens, outputTokens, body.model, 0).catch((e) =>
                console.error('charge failed', e),
              );
            },
          },
        });

        if (refusalText !== null) {
          writer.write('refusal', { text: refusalText });
        } else {
          writer.write('done', { tree: workingTree });
        }
      } catch (err) {
        console.error('agent-proxy stream error', err);
        const message = err instanceof Error ? err.message : String(err);
        writer.write('error', { code: 'vibe_upstream_error', message });
      } finally {
        writer.close();
      }
    },
  });

  return new Response(stream, { headers: { ...SSE_HEADERS, ...corsHeaders } });
});
