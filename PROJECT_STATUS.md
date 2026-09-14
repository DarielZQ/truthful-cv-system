# Project Status

## Implemented result

The Level-2 release candidate implements this private pipeline:

```text
selected URL/paste -> normalized snapshot -> requirements_review -> approved
-> assessed + vacancy-bound exact-line manifest -> rendered + artifact hash
-> later visual approval -> finalized hash-identical deliverable
```

Implemented controls include typed evidence and exact-line signatures; structure-preserving heuristic requirement extraction; personal/legal hard filters; retrieval-only tag matching with reasoned human semantic overrides; deterministic exact-line tailoring; strict PDF checks; two-stage byte-bound visual approval; hashes binding approved requirements, the tailored manifest, render input, and PDF; strict workflow transitions; lock-protected canonical/provider/content-hash deduplication; and centralized private-root traversal/symlink/reparse containment.

Public retrieval is limited to documented Greenhouse Job Board API GET and Lever Postings API JSON GET adapters. LinkedIn, Indeed, Glassdoor, Workday, Costa Rica portals, and arbitrary employer pages are paste-only by default. An arbitrary page requires an exact operator `--allow-public-host` opt-in after permission review. There is no authentication, POST, JavaScript, liveness verification, or application submission.

## Verification

Current release verification: `245 passed`, Ruff clean, `uv lock --check` clean, and `git diff --check` clean. The suite includes offline Greenhouse/Lever transport contracts and an actual sanitized RenderCV `2.8` end-to-end execution. An independent fail-closed review found no critical or high-severity release blockers. One-page output is not promised; the strict verifier enforces the configured maximum.

## Privacy boundary

Committed files are reusable source, tests, documentation, and synthetic samples. Candidate data, sources, vacancy records, generated YAML/PDFs, and deliverables remain in ignored local paths.
