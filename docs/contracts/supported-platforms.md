# Astrid Supported Platforms — m8 packaged GA release matrix

**Artifact status:** the m8 release matrix is frozen for the packaged GA gate;
the m4 development matrix is retained below as historical evidence.

**Normative sources:** `docs/astrid-v10-implementation-decisions.md` §19
(m8 packaged GA release contract), the m8 plan (Step 1, decision artifact),
and `docs/contracts/platform-contract.md` (the v1 public SDK boundary, which
this document does not change).

**Purpose:** freeze the m8 **packaged release matrix** — the platforms,
installed artifact, browser, clean-account conditions, publication boundary,
and evidence ownership that the GA gate may claim. Anything not listed here is
unsupported and must not be silently treated as tested.

---

## 1. Frozen m8 release matrix

| Dimension | Target | Evidence and release meaning |
|---|---|---|
| Release OS | **Linux and macOS** | Both are blocking release targets. Windows is unsupported for m8 and is not represented by emulation or metadata-only evidence. |
| Python (CPython) | **3.11 and 3.12** | Every declared OS/Python target installs and exercises the same wheel outside the source checkout. |
| Browser | **current stable Chromium** | The editor-contract lane uses Chromium. Firefox, Safari, and Edge are unsupported m8 browser targets. |
| Package | **Python distribution `astrid`** | The release artifact is one wheel built from this repository; its contents, SHA-256, installed path, and version are recorded for every lane. |
| Version | **`0.1.0` for this release** | The version is sourced from `pyproject.toml` and is identical in the wheel metadata, installed package, and evidence. Future releases must update that single source before the gate runs. |
| Publication | **local release artifact directory only** | The wheel is retained as a local release artifact for the gate and handoff. No PyPI, cloud registry, hosted publication, or external upload is authorized by m8. |
| macOS signing/notarization | **unsigned and unnotarized** | The local wheel is documented as unsigned and unnotarized. It is not Gatekeeper-ready, notarized, signed, or an installer/application bundle. No signing credential is assumed. |
| Clean account | **fresh credential-free local account** | Each run uses isolated home, state, project, media, cache, configuration, and browser-profile paths with account, cloud, and provider credentials/configuration absent. It proves the installed product's local-first journey, not a pre-seeded or authenticated environment. |
| Evidence owner | **Astrid Release Owner** | The role owns the matrix, evidence completeness, digest consistency, and ship decision. CI lane owners produce automated records; the designated physical-device operator retains manual device records under the Release Owner's custody. |

The release dependency and toolchain inputs are frozen by the hashed locks and
machine-readable evidence described in
[`docs/runbooks/reproducible-release.md`](../runbooks/reproducible-release.md).
The label "current stable Chromium" is realized by the exact Playwright package
and Chromium revision recorded by each matrix cell; it is never resolved from
an unpinned `npx` invocation.

### 1.1 Evidence classification

- **Blocking automated evidence:** installed-wheel packaging, import/help/version
  checks, runtime contract and credential-free journey checks, authority and
  factoring scans, and the current stable Chromium editor-contract checks on
  each declared Linux/macOS and CPython 3.11/3.12 automated lane. Each record
  must identify the same wheel SHA-256 and installed artifact path.
- **Retained physical-device evidence:** a clean-account editor journey on a
  real macOS device using current stable Chromium, including the actual
  browser opening and local filesystem behavior. This evidence is retained and
  owned by the Release Owner; automated tests cannot be relabeled as physical
  device proof.
- **Signing evidence:** none is expected or accepted for this m8 artifact.
  Absence of signing/notarization is a declared release fact, not a failed
  claim that may be hidden by a CI result.

### 1.2 Release boundary

The m8 gate may publish acceptance, authority, performance, clean-account,
handoff, and ship artifacts only when all blocking automated evidence is green,
the required physical-device evidence is retained, and every record points to
the same `astrid` 0.1.0 wheel digest. A source-tree test, a different wheel,
an authenticated account, a simulated macOS run, or an unsigned artifact
described as notarized does not satisfy this contract.

## 2. Frozen m4 development matrix (historical)

| Dimension | Target | Notes |
|---|---|---|
| CI OS | **Linux** | Linux is the only m4 CI OS. macOS and Windows are **not** m4 targets. |
| Python (CPython) | **3.11 and 3.12** | CI must actually execute both Python targets (install + test), not merely assert them. |
| Development install | **editable installation** | The development gate installs the package editable (`pip install -e '.[dev]'`); wheel/standalone packaging is an m6 concern. |
| Node.js | **20.19** (floor) | Pinned floor for the external editor lane tooling; the observed dev environment runs Node v20.20.2, which satisfies the floor. |
| Browser (external editor lane) | **current stable Chromium** | Used only by the external Reigh editor evidence lane (disposition reporting; never an m4 admission input). |
| Release Owner | **the Astrid Release Owner role** | Named role per `docs/astrid-v10-implementation-decisions.md` §9; assigning an individual is an organizational follow-up. |
| Deadline | **end of Sprint 5** (before Sprint 6 Phase 2 work begins) | The frozen deadline for the matrix owner to deliver the release packaging/platform decision. |

## 3. What m4 CI actually executed

- The m4 gate CI must run the retained evidence lanes on **both** CPython 3.11
  and CPython 3.12 (Linux), with the package installed **editable**.
- The external editor lane (pinned Reigh selectors + latency check) must run as
  an always-run **disposition-reporting** lane on Linux with the pinned Node
  floor and current stable Chromium. It is retained evidence and is **never** an
  input to m4 admission success.

## 4. Explicitly out of scope for m4

- macOS and Windows CI, Firefox/Safari, wheel/standalone distribution,
  Python 3.13+, Node LTS lines other than the 20.19 floor, and non-Chromium
  browsers are **not** m4 targets.
- Broader release packaging, additional OS targets, and a production browser
  matrix are **m6 release packaging** concerns. The Astrid Release Owner is
  responsible for that decision by the end of Sprint 5 (§1).

## 5. Relationship to other contracts

- `docs/contracts/platform-contract.md` remains the normative v1 public SDK
  boundary (export surface, SemVer, trust model). This document adds the m4
  development-matrix targets; it does not amend the v1 boundary.
- The platform regression lane (m4 Step 15) asserts the frozen OS, browser,
  Python, Node, and development-install targets above, including the Release
  Owner and Sprint-5 deadline.

---

**Record of amendments:** m8 amendment 1 adds the packaged GA release matrix
above and makes it the current release authority; the historical m4 matrix is
unchanged. Any future change to a frozen value must be logged here with its
v10 amendment reference.
