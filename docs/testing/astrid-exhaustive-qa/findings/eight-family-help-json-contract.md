# Eight-family help and JSON contract finding

Date: 2026-08-24  
Severity: P2 documentation/ergonomics (fixed); separate P1 runtime follow-up

Cold-start agents were told both that all eight families were available and
that `--json` always meant the exact five-key SDK envelope. Product help was
also missing several public verbs. Live help replay showed the actual contract:
product/nested commands use `ok/data/error/receipt/idempotency_key`, `doctor
--json` intentionally returns diagnostics (`ok/state/checks/next_action`), and
`serve`/`backup` have no JSON flag. The summaries also needed
`projects current`, `timelines unarchive`, `timelines visualize`, and
`timelines render`.

The gateway help, core skill, CLI contract, and CLI journey guide now describe
the same contract. A stale journey save example was replaced with a canonical
renderable timeline config, and copyable visualize/render examples were added.
Focused help/domain/doctor/selection checks passed (13 + 80 tests).

Independent of that documentation fix, the live wave exposed a P1 candidate:
after public `media references create`, visualization fails to open the
database with `applied migrations for pack 'references', which is not
registered in this composition`. This remains for a separate runtime fix and
must not be mistaken for a help-only PASS.
