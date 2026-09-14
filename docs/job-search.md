# Job-search workflow

## Capture

1. Select an HTTPS URL. LinkedIn, Indeed, Glassdoor, Workday, Costa Rica portals, and arbitrary employer pages are paste-only by default.
2. Recognized Greenhouse URLs use the read-only Job Board API GET; recognized Lever URLs use the public Postings API JSON GET. For another public employer host, first verify anonymous GET is permitted, then pass that exact hostname with `--allow-public-host`.
3. Use `--paste-file`, title, and employer to resume `pending_capture`. Line and list boundaries are preserved.
4. The normalized private snapshot stores provenance, provider identity, metadata, description, `content_hash`, and policy reason—not raw HTML, headers, cookies, or scripts. Canonical URLs retain semantic query parameters and remove only a conservative tracking allowlist. Canonical, provider/external, and content hashes deduplicate under locks.

## Review and assessment

1. Review every deterministic heuristic draft in `requirements.yaml`. Required/preferred/responsibility headings influence subsequent unpunctuated bullets. Personal/legal kinds default to hard filters.
2. Approve/reject explicitly. Assessment requires tracker status `approved` and no pending requirements.
   Approval hashes the exact requirements file; later edits invalidate assessment. An unresolved hard filter stops assessment until a truthful, reasoned human adjudication is recorded.
3. Run `vacancy assess --base-manifest ...` with a private reviewed library whose exact lines are signed in the profile.
4. Tag overlap retrieves approved claims but is not semantic proof. Machine matching is only `absent` or `partial`; `strong`/`deep` requires a nonblank human rationale. Coverage and hard-filter failures use the adjudicated level.
5. Assessment preserves structural headline/summary lines and ranks evidence lines deterministically by required/preferred tag overlap. It writes and tracker-binds an exact-line vacancy subset. It never creates or signs wording.

## Rendering and visual approval

The first `vacancy finalize` invocation requires `assessed`, renders once with pinned RenderCV and absolute private paths, runs strict verification, stores `rendered` and the artifact SHA-256, and returns `visual_approval_required`. Inspect the generated PDF.

A later invocation with `--visual-approved` requires that prior state, verifies current bytes equal the stored hash, reruns strict verification, copies, compares hashes, and records `finalized`. It never rerenders. The verifier enforces a configured page maximum; tailoring cannot guarantee one page.

This system does not re-check liveness and does not submit applications. Any application action is separate and manual.
