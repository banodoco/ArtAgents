# Astrid Supported Platforms — m4 development matrix (frozen)

**Artifact status:** frozen for milestone m4 (Sprints 4–5).

**Normative sources:** `docs/astrid-v10-implementation-decisions.md` §9
(Release Owner and Sprint-5 deadline); the m4 plan (Step 2, decision artifact);
`docs/contracts/platform-contract.md` (the v1 public SDK boundary, which this
document does not change).

**Purpose:** freeze the conservative m4 **development matrix** — the platforms
the m4 gate and CI actually execute — and distinguish it from m6 release
packaging. This matrix is the authoritative answer to "what must pass in m4";
anything not listed here is explicitly out of scope for the m4 gate even if it
is a later-milestone target.

---

## 1. Frozen m4 matrix

| Dimension | Target | Notes |
|---|---|---|
| CI OS | **Linux** | Linux is the only m4 CI OS. macOS and Windows are **not** m4 targets. |
| Python (CPython) | **3.11 and 3.12** | CI must actually execute both Python targets (install + test), not merely assert them. |
| Development install | **editable installation** | The development gate installs the package editable (`pip install -e '.[dev]'`); wheel/standalone packaging is an m6 concern. |
| Node.js | **20.19** (floor) | Pinned floor for the external editor lane tooling; the observed dev environment runs Node v20.20.2, which satisfies the floor. |
| Browser (external editor lane) | **current stable Chromium** | Used only by the external Reigh editor evidence lane (disposition reporting; never an m4 admission input). |
| Release Owner | **the Astrid Release Owner role** | Named role per `docs/astrid-v10-implementation-decisions.md` §9; assigning an individual is an organizational follow-up. |
| Deadline | **end of Sprint 5** (before Sprint 6 Phase 2 work begins) | The frozen deadline for the matrix owner to deliver the release packaging/platform decision. |

## 2. What CI must actually execute

- The m4 gate CI must run the retained evidence lanes on **both** CPython 3.11
  and CPython 3.12 (Linux), with the package installed **editable**.
- The external editor lane (pinned Reigh selectors + latency check) must run as
  an always-run **disposition-reporting** lane on Linux with the pinned Node
  floor and current stable Chromium. It is retained evidence and is **never** an
  input to m4 admission success.

## 3. Explicitly out of scope for m4

- macOS and Windows CI, Firefox/Safari, wheel/standalone distribution,
  Python 3.13+, Node LTS lines other than the 20.19 floor, and non-Chromium
  browsers are **not** m4 targets.
- Broader release packaging, additional OS targets, and a production browser
  matrix are **m6 release packaging** concerns. The Astrid Release Owner is
  responsible for that decision by the end of Sprint 5 (§1).

## 4. Relationship to other contracts

- `docs/contracts/platform-contract.md` remains the normative v1 public SDK
  boundary (export surface, SemVer, trust model). This document adds the m4
  development-matrix targets; it does not amend the v1 boundary.
- The platform regression lane (m4 Step 15) asserts the frozen OS, browser,
  Python, Node, and development-install targets above, including the Release
  Owner and Sprint-5 deadline.

---

**Record of amendments:** none yet. Any change to a frozen value above must be
logged here with its v10 amendment reference.
