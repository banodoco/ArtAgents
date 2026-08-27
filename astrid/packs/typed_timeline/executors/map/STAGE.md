# typed_timeline.map — Stage

Admits one kernel run+child task, then maps host-admitted inline rows or a
project-owned JSON artifact into `timeline.json`, `assets.json`, and optional
tone audio in the assigned staging directory. The pack never imports another
pack repository, opens SQLite, invents a filesystem run ledger, or accepts an
unowned path. `runaway` is a row-contract name, not a database capability.
Frames prefer `metadata.frame` and fall back to `start_ms`; invalid/duplicate
events fail closed. The result manifest contains staging-relative output paths
and content hashes, so it is portable across machines.
