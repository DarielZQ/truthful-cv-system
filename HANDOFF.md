# Handoff

## State

The candidate-neutral project tree implements profile and manifest validation, requirement matching, RenderCV YAML generation, strict PDF verification, and atomic private job tracking. The first-release candidate has passed the automated and artifact checks recorded in `PROJECT_STATUS.md`. Release commits are created only after an independent fail-closed review of the exact staged tree.

## Data locations

- Public implementation: `src/truthful_cv/`
- Public synthetic tests: `tests/`
- Public sanitized inputs: `samples/`
- Public schema description: `docs/profile-schema.md`
- Spanish Windows guide: `docs/GUIA_USO_ES.md`
- Private source register, profile, and manifests: `profile/private/`
- Private research, generated output, and deliverables: `private/`, `generated/`, and `deliverables/`

Private paths are ignored by Git. Validation and builds must never rewrite private factual claims except when a user deliberately saves an approved private change.

## Setup and quality checks

From the repository root:

```bash
uv sync --extra dev --extra render --locked
uv run pytest
uv run ruff check .
git diff --check
```

The sanitized sample is validated by `tests/test_samples.py`. Operational commands are documented in the README and Spanish guide.

## Core CLI

```bash
uv run truthful-cv validate-profile \
  --profile profile/private/master-profile.yaml \
  --sources profile/private/source-register.yaml

uv run truthful-cv build \
  --profile profile/private/master-profile.yaml \
  --sources profile/private/source-register.yaml \
  --manifest profile/private/manifests/master.yaml \
  --output generated/master/input.yaml

uv run truthful-cv verify-pdf \
  --profile profile/private/master-profile.yaml \
  --sources profile/private/source-register.yaml \
  --manifest profile/private/manifests/master.yaml \
  --pdf generated/master/rendercv_output/candidate-cv.pdf
```

`verify-pdf` returns nonzero for malformed profile or manifest input, unreadable PDFs, configured redlines after text normalization, missing required rendered strings, excessive page count, or an insufficient text layer. Expected input failures are concise and path-free; unexpected programming exceptions are allowed to surface for debugging.

## Implemented invariants

- Approved claims require registered sources and cannot use Tier D.
- Claim categories and role categories use explicit controlled values.
- Role and education dates accept four-digit years or valid `YYYY-MM` values.
- Required profile and outward-facing manifest strings reject whitespace-only values.
- Claim, source, role, and education IDs are checked for duplicates where applicable.
- Claim and manifest subject references must resolve to the required entity kind.
- Exported lines must use approved claims and exact signatures that bind rendered profile facts.
- Role category controls whether output appears in experience or structured training.
- PDF verification checks normalized redlines and the expected rendered-string inventory.
- Job tracking uses a lock and atomic replacement.

## Release constraints

- Review the exact staged file list before committing.
- Confirm the Git object database contains no sensitive unreachable objects.
- Create only a new private repository; never overwrite, force-push, or change visibility automatically.
- Keep application submission manual.
