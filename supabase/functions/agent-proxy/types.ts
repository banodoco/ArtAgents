// Vibe Mode agent-proxy — shared types.
//
// Mirror of `banodoco-website/src/types/vibe.ts` for Deno/Edge
// consumption. Keep field names byte-identical so request/response
// bodies serialise without translation.

export interface VirtualFile {
  path: string;
  kind: 'text' | 'binary-asset';
  mime: string;
  content?: string;
  assetId?: string;
}

export type VirtualFileTree = Record<string, VirtualFile>;

export type ChatPart =
  | { type: 'text'; text: string }
  | { type: 'image'; assetId: string; mime: string; width?: number; height?: number }
  | { type: 'system_notice'; text: string }
  | { type: 'tool_call'; tool: 'write_file' | 'apply_patch'; path: string }
  | { type: 'tool_result'; ok: boolean; summary: string };

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  createdAt: string;
  parts: ChatPart[];
  snapshotId?: string | null;
}

export type VibeModel =
  | 'claude-sonnet-4-6'
  | 'claude-opus-4-7'
  | 'claude-haiku-4-5';

export interface UserTurnInput {
  text: string;
  images?: Array<{ mime: string; dataUrl: string; width: number; height: number }>;
}

export interface AgentProxyRequestBody {
  postDraftId: string;
  model: VibeModel;
  tree: VirtualFileTree;
  chatHistory: ChatMessage[];
  userTurn: UserTurnInput;
  templateContinuation?: string | null;
}

export type ToolUseCall =
  | { id: string; name: 'write_file'; input: { path?: unknown; content?: unknown } }
  | { id: string; name: 'apply_patch'; input: { path?: unknown; search?: unknown; replace?: unknown } }
  | { id: string; name: string; input: Record<string, unknown> };

export interface ToolResultSummary {
  tool_use_id: string;
  tool: string;
  path: string;
  ok: boolean;
  summary: string;
  error?: string;
}
