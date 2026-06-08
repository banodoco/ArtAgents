# builtin.agent_probe

Legacy task-mode probe orchestrator used by regression tests.

## Purpose

Walks through test items (alpha, beta, gamma) generating per-item verdict files.
Used by agentic test scenarios to verify task-mode orchestration behavior.

## Usage

```bash
python3 -m astrid orchestrators run builtin.agent_probe --out ./out
```
