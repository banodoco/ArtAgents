# REWORK batch 2 attempt 2 — fix ghost admission + fallback

## Tasks
### Fix kernel_admission.py
- Fix DatabaseWriter(root) → DatabaseWriter(db_path, registry)
- Remove ensure_database import
- Fix EventAppendService import path
- Ensure admit returns kernel ids

### Fix sdk.invoke fallback
- Delete fallback block, let kernel failures raise

### Fix orchestrator ledger
- Demote orchestrator runner ledger

