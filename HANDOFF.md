# Handoff

## State

The uncommitted Level-2 tree is intended for a second independent review. Do not commit or push it before that review.

## Commands

```bash
uv sync --extra dev --extra render --locked
uv run pytest -p no:cacheprovider
uv run ruff check .
uv lock --check
git diff --check

uv run truthful-cv vacancy ingest --url URL --private-root private [--paste-file FILE] [--title TITLE] [--employer EMPLOYER] [--allow-public-host EXACT_HOST]
uv run truthful-cv vacancy approve-requirements --job JOB-001 --private-root private --approve REQ-001 REQ-002
uv run truthful-cv vacancy assess --job JOB-001 --private-root private --profile PROFILE --sources SOURCES --base-manifest PRIVATE_SIGNED_LIBRARY
uv run truthful-cv vacancy finalize --job JOB-001 --private-root private --profile PROFILE --sources SOURCES
# inspect the generated PDF bytes, then run without changing them:
uv run truthful-cv vacancy finalize --job JOB-001 --private-root private --profile PROFILE --sources SOURCES --visual-approved
```

## Invariants

- Required transitions are `requirements_review -> approved -> assessed -> rendered -> finalized`; tracker updates reject skips, regressions, and cross-phase transitions.
- Approval stores the exact requirements-file hash and assessment checks it against the captured snapshot. Rendering stores the tailored-manifest and generated-input hashes as well as the PDF hash; visual approval rejects any changed component.
- Assessment ranks only exact signed lines from the supplied private base library and binds a relative vacancy-specific manifest reference.
- Tag overlap retrieves approved claims but machine levels never exceed `partial`. Human `strong`/`deep` overrides require rationale.
- Personal/legal requirement kinds default to `hard_filter: true`; unresolved `absent`/`partial` filters fail assessment.
- The first finalize call renders and stores the artifact SHA-256. The approval call does not rerender; it verifies the stored bytes again before a hash-identical copy.
- All workflow artifacts stay beneath the resolved private root and reject traversal and symlink/reparse escapes.
- Renderer output is captured, expected errors are fixed/path-free, and application submission is outside the system.

## Retrieval

Only recognized Greenhouse and Lever public URLs map to documented read-only JSON GET APIs. LinkedIn, Indeed, Glassdoor, Workday, Costa Rica portals, and arbitrary employer pages are paste-only by default. Arbitrary GET requires exact `--allow-public-host` operator opt-in. No POST, authentication, cookies, JavaScript, or protection bypass exists.
