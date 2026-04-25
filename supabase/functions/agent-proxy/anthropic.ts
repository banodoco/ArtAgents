// Anthropic SDK wrapper for the Vibe Mode agent-proxy.
//
// Uses `@anthropic-ai/sdk` via the Deno `npm:` specifier declared in
// `./deno.json` so SSE parsing, tool-use streaming, and cache_control
// breakpoints are handled by the SDK rather than hand-rolled.
//
// Prompt-cache design — EXACTLY two breakpoints per turn:
//   1. system + tools (keyed so it never changes between turns)
//   2. <file_tree> XML content part on the turn-1 user message
// Any further content parts (text, images) intentionally stay
// uncached so that incremental author input remains cheap.

import Anthropic from '@anthropic-ai/sdk';
import { serializeTreeForClaude } from './fileTreeXml.ts';
import { TOOL_SCHEMAS } from './tools.ts';
import type {
  ChatMessage,
  ChatPart,
  ToolUseCall,
  UserTurnInput,
  VibeModel,
  VirtualFileTree,
} from './types.ts';

export interface StreamCallbacks {
  onText(delta: string): void;
  onToolUse(call: ToolUseCall): void;
  onStop(stop: { stop_reason: string | null; usage: Anthropic.Messages.Usage | null; finalText: string }): void;
}

const PRICING: Record<VibeModel, { input: number; output: number }> = {
  // USD per 1M tokens — conservative defaults; adjust if Anthropic publishes revised rates.
  'claude-sonnet-4-6': { input: 3, output: 15 },
  'claude-opus-4-7': { input: 15, output: 75 },
  'claude-haiku-4-5': { input: 0.8, output: 4 },
};

export const estimateUsdCost = (
  model: VibeModel,
  usage: { input_tokens: number; output_tokens: number },
): number => {
  const pricing = PRICING[model];
  return (
    (usage.input_tokens * pricing.input) / 1_000_000 +
    (usage.output_tokens * pricing.output) / 1_000_000
  );
};

type AnthropicContent = Anthropic.Messages.MessageParam['content'];

// Build the priors — every prior chat message, in role order. We never
// add cache_control breakpoints to priors; they're implicitly cached by
// the turn-1 file_tree breakpoint when identical.
const buildPriorMessages = (chatHistory: ChatMessage[]): Anthropic.Messages.MessageParam[] => {
  const msgs: Anthropic.Messages.MessageParam[] = [];
  for (const m of chatHistory) {
    if (m.role !== 'user' && m.role !== 'assistant') continue;
    const parts: AnthropicContent = [];
    for (const part of m.parts) {
      if (part.type === 'text' && part.text) {
        parts.push({ type: 'text', text: part.text });
      }
    }
    if (Array.isArray(parts) && parts.length > 0) {
      msgs.push({ role: m.role, content: parts });
    }
  }
  return msgs;
};

// Pull asset paths out of the ChatBar-prefixed attachment blurb. Only
// treats a line as an attachment when the surrounding message contains
// "I've attached" so arbitrary markdown lists in user text don't false-
// positive.
const ATTACHMENT_HEADER = "I've attached";
const ATTACHMENT_LINE_RE = /^- `(assets\/[^`]+)`/gm;
const extractAttachmentPaths = (text: string): string[] => {
  if (!text.includes(ATTACHMENT_HEADER)) return [];
  const paths: string[] = [];
  ATTACHMENT_LINE_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = ATTACHMENT_LINE_RE.exec(text)) !== null) {
    paths.push(match[1]);
  }
  return paths;
};

// Emit a <recent_attachments> block (or null when nothing's been attached)
// so the agent gets a high-signal reminder of which assets the author
// added and when — attachment notices were previously buried inside the
// prior user-message text and could be overlooked, producing confabulated
// "it didn't come through" replies on follow-up turns.
const buildRecentAttachmentsBlock = (
  chatHistory: ChatMessage[],
  currentUserText: string,
): string | null => {
  type Source = { text: string; turnsAgo: number };
  const sources: Source[] = [{ text: currentUserText, turnsAgo: 0 }];
  let turnsAgo = 1;
  for (let i = chatHistory.length - 1; i >= 0; i -= 1) {
    const m = chatHistory[i];
    if (m.role !== 'user') continue;
    const text = m.parts
      .filter((p): p is Extract<ChatMessage['parts'][number], { type: 'text' }> => p.type === 'text')
      .map((p) => p.text)
      .join('\n');
    if (text) {
      sources.push({ text, turnsAgo });
      turnsAgo += 1;
    }
  }

  const earliest = new Map<string, number>();
  for (const source of sources) {
    for (const path of extractAttachmentPaths(source.text)) {
      const prev = earliest.get(path);
      if (prev === undefined || source.turnsAgo < prev) earliest.set(path, source.turnsAgo);
    }
  }
  if (earliest.size === 0) return null;

  const formatAdded = (n: number): string => {
    if (n === 0) return 'this turn';
    if (n === 1) return 'previous turn';
    return `${n} turns ago`;
  };
  const escape = (v: string): string =>
    v.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const entries = [...earliest.entries()].sort((a, b) => a[1] - b[1]);
  const lines = entries.map(
    ([path, t]) => `  <attachment path="${escape(path)}" added="${escape(formatAdded(t))}"/>`,
  );
  return `<recent_attachments>\n${lines.join('\n')}\n</recent_attachments>`;
};

const buildTurnMessage = (
  tree: VirtualFileTree,
  chatHistory: ChatMessage[],
  userTurn: UserTurnInput,
  isFirstTurn: boolean,
): Anthropic.Messages.MessageParam => {
  // `unknown as` because the Anthropic SDK's ContentBlockParam union
  // doesn't expose cache_control in the shipped types for every shape,
  // but the API accepts it on any content block.
  //
  // Note: the template continuation is NOT appended here — per doc §Step 5
  // it is appended to SYSTEM_PROMPT_V1 on turn 1 only (see systemPrompt.ts
  // `buildSystemPromptForTurn`). Keeping it out of the user message means
  // the <file_tree> cache block can share an exact prefix across turns.
  const parts: Array<Record<string, unknown>> = [];

  if (isFirstTurn) {
    parts.push({
      type: 'text',
      text: serializeTreeForClaude(tree),
      // Cache breakpoint #2 — <file_tree> XML on turn 1 only.
      cache_control: { type: 'ephemeral' },
    });
  } else {
    parts.push({
      type: 'text',
      text: serializeTreeForClaude(tree),
    });
  }

  // <recent_attachments> sits AFTER the file_tree so the turn-1 cache
  // breakpoint is unaffected; it's a per-turn hint and legitimately
  // varies, so it must not be inside the cached prefix.
  const recentAttachments = buildRecentAttachmentsBlock(chatHistory, userTurn.text);
  if (recentAttachments) {
    parts.push({ type: 'text', text: recentAttachments });
  }

  if (userTurn.images) {
    for (const img of userTurn.images) {
      parts.push({
        type: 'image',
        source: { type: 'base64', media_type: img.mime, data: img.dataUrl.replace(/^data:[^,]+,/, '') },
      });
    }
  }

  parts.push({ type: 'text', text: userTurn.text });

  return {
    role: 'user',
    content: parts as unknown as AnthropicContent,
  };
};

export interface RunStreamOptions {
  apiKey: string;
  model: VibeModel;
  // Must be the effective prompt for the current turn, i.e. SYSTEM_PROMPT_V1
  // plus any turn-1 template continuation appended. Callers should use
  // `buildSystemPromptForTurn(isFirstTurn, templateContinuation)` from
  // `./systemPrompt.ts` to compute this.
  systemPrompt: string;
  tree: VirtualFileTree;
  chatHistory: ChatMessage[];
  userTurn: UserTurnInput;
  callbacks: StreamCallbacks;
  signal?: AbortSignal;
}

/**
 * Run one turn through the Anthropic Messages streaming API.
 *
 * Streams `text` deltas via `callbacks.onText`. Buffers `tool_use`
 * blocks fully and emits them via `callbacks.onToolUse` only after
 * `message_stop`, per Vibe Mode's "narrate-then-batch" rule.
 */
export const runAgentTurn = async (opts: RunStreamOptions): Promise<void> => {
  const client = new Anthropic({ apiKey: opts.apiKey });
  const isFirstTurn = opts.chatHistory.length === 0;

  const priors = buildPriorMessages(opts.chatHistory);
  const turnMsg = buildTurnMessage(opts.tree, opts.chatHistory, opts.userTurn, isFirstTurn);

  const messages: Anthropic.Messages.MessageParam[] = [...priors, turnMsg];

  // Cache breakpoint #1 — system + tools block.
  const systemBlock = [
    {
      type: 'text' as const,
      text: opts.systemPrompt,
      // deno-lint-ignore no-explicit-any
      cache_control: { type: 'ephemeral' } as any,
    },
  ];

  const stream = client.messages.stream(
    {
      model: opts.model,
      max_tokens: 8192,
      system: systemBlock,
      tools: TOOL_SCHEMAS as unknown as Anthropic.Messages.Tool[],
      messages,
    },
    { signal: opts.signal },
  );

  // Accumulator for tool_use blocks; applied only after message_stop.
  const pendingTools = new Map<number, { id: string; name: string; inputJson: string }>();
  let finalText = '';

  stream.on('text', (delta: string) => {
    finalText += delta;
    opts.callbacks.onText(delta);
  });

  stream.on('streamEvent', (event: Anthropic.Messages.MessageStreamEvent) => {
    if (event.type === 'content_block_start' && event.content_block.type === 'tool_use') {
      pendingTools.set(event.index, {
        id: event.content_block.id,
        name: event.content_block.name,
        inputJson: '',
      });
    } else if (event.type === 'content_block_delta' && event.delta.type === 'input_json_delta') {
      const existing = pendingTools.get(event.index);
      if (existing) {
        existing.inputJson += event.delta.partial_json;
      }
    }
  });

  const finalMessage = await stream.finalMessage();

  // Flush buffered tool calls after message_stop.
  for (const [, pending] of pendingTools) {
    let parsed: Record<string, unknown> = {};
    try {
      parsed = pending.inputJson ? JSON.parse(pending.inputJson) : {};
    } catch (_err) {
      parsed = {};
    }
    opts.callbacks.onToolUse({ id: pending.id, name: pending.name, input: parsed } as ToolUseCall);
  }

  opts.callbacks.onStop({
    stop_reason: finalMessage.stop_reason ?? null,
    usage: finalMessage.usage ?? null,
    finalText,
  });
};

// Re-expose the ChatPart shape so index.tsx can construct chat updates
// without pulling it from `./types` twice.
export type { ChatPart };
