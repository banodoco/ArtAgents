# Cloud custody receipt — E0.3

Operation: `astrid-canonical-pack-beta-20260831-a1`

- Source worktree:
  `/Users/peteromalley/Documents/reigh-workspace/Astrid-canonical-pack-beta`
- Remote repository:
  `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
- Branch: `megado/canonical-pack-beta`
- Verified HEAD: `7ac50c12e8e4d90988fee603ffdb9896e5628792`
- Git bundle SHA-256:
  `ab229d03e365933ba1bd14a0a77c775e586eac261898925eaa1250d17d8aee0e`
- Complete `.oracle` overlay archive SHA-256:
  `4783ee3ee2a928c76bd08e748507479104a703d8b090e4f31d658b12a31fe544`
- Sorted `.oracle` file manifest SHA-256:
  `4c6a50bd68da1b1cade1495c1ab0559e6682bd20b79bbb0b2d224f30d82b6dc6`
- `.oracle` source file count: 755 (excluding generated `__pycache__`)
- Bundle size: 181 MiB
- Overlay size: 11 MiB
- Remote `git bundle verify`: PASS
- Remote archive digests/file manifest: PASS
- Remote exact-HEAD assertion: PASS
- Remote product diff outside `.oracle`: zero
- Transfer artifact cleanup: 102 macOS-generated AppleDouble `._*` files were
  removed from the isolated remote overlay; the resulting count matches the
  755-file source manifest.
- Original dirty checkout touched: no
- Ordinary branch push used for transfer: no

The full archive digest is necessarily recorded outside the archive and in the
machine operation ledger because an archive cannot contain its own stable
digest. This receipt was copied separately into the verified remote checkout.
