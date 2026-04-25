// Vibe Mode — advisory safety scanner.
//
// Runs AFTER the model's tool batch has been applied to the virtual file
// tree. Emits `safety_warning` SSE events when it spots patterns that
// could indicate exfiltration, leaked credentials, or unsafe runtime
// behaviour inside the authored bundle. NEVER blocks a turn — findings
// are surfaced in chat so the author (and downstream admin reviewer) can
// judge intent before Ship It.
//
// Regex list is fixed by the Vibe Mode plan's pre-plan guidance. Do not
// tune without reviewer flag.

import type { VirtualFileTree, VirtualFile } from './types.ts';

export interface SafetyFinding {
  path: string;
  rule: 'suspicious_api_key' | 'exfil_url' | 'eval_in_js' | 'iframe_breakout';
  excerpt: string;
}

const RULES: Array<{ rule: SafetyFinding['rule']; pattern: RegExp }> = [
  {
    rule: 'suspicious_api_key',
    pattern: /(?:sk|pk|anthropic|openai)[-_][a-zA-Z0-9]{20,}/i,
  },
  {
    rule: 'exfil_url',
    pattern:
      /https?:\/\/(?!localhost|127\.0\.0\.1|banodoco\.com)[^\s"'<>]+\/[^\s"'<>]*(?:api|webhook|collect|track)[^\s"'<>]*/i,
  },
  {
    rule: 'eval_in_js',
    pattern: /\b(?:eval|Function)\s*\(/,
  },
  {
    rule: 'iframe_breakout',
    pattern: /(?:window\.top|parent\.(?:location|postMessage))/,
  },
];

const EXCERPT_RADIUS = 40;

const scanContent = (path: string, content: string): SafetyFinding[] => {
  const findings: SafetyFinding[] = [];
  for (const { rule, pattern } of RULES) {
    const match = content.match(pattern);
    if (match && typeof match.index === 'number') {
      const start = Math.max(0, match.index - EXCERPT_RADIUS);
      const end = Math.min(content.length, match.index + match[0].length + EXCERPT_RADIUS);
      findings.push({ path, rule, excerpt: content.slice(start, end) });
    }
  }
  return findings;
};

export const scanTree = (tree: VirtualFileTree): SafetyFinding[] => {
  const findings: SafetyFinding[] = [];
  for (const path of Object.keys(tree).sort()) {
    const file: VirtualFile = tree[path];
    if (file.kind !== 'text' || typeof file.content !== 'string') continue;
    findings.push(...scanContent(path, file.content));
  }
  return findings;
};

export const describeFinding = (finding: SafetyFinding): string => {
  switch (finding.rule) {
    case 'suspicious_api_key':
      return `Possible API-key-shaped string in ${finding.path}: "${finding.excerpt}"`;
    case 'exfil_url':
      return `External URL to a non-allowlisted API/webhook/track/collect endpoint in ${finding.path}: "${finding.excerpt}"`;
    case 'eval_in_js':
      return `Use of eval/Function constructor in ${finding.path}: "${finding.excerpt}"`;
    case 'iframe_breakout':
      return `Iframe-breakout pattern (window.top / parent.*) in ${finding.path}: "${finding.excerpt}"`;
  }
};
