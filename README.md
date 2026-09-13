# Truthful CV System

A private-first, evidence-based system for maintaining a canonical professional profile, assessing job fit, and producing tailored ATS-readable CVs without inventing qualifications.

## Design

- A typed claim and evidence registry is the source of truth.
- The private authoring manifest retains claim lineage and must match an exact approved-line signature; the exported RenderCV document deliberately omits internal claim IDs.
- Job requirements are scored only against approved evidence.
- RenderCV `2.8` is a pinned output adapter, not the profile database.
- Generated applications remain human-reviewed and are never auto-submitted by default.
- Profiles, source extracts, vacancy snapshots, generated files, and deliverable PDFs are excluded from Git.

## Status

The end-to-end local workflow is operational. It includes profile/reference validation, manifest policy gates, requirement matching, relevance ranking, RenderCV conversion, PDF checks, private job tracking, and a tested CLI. Candidate-specific counts, vacancy findings, filenames, and application decisions remain in ignored private records.

The first-release candidate passed 150 automated tests, Ruff, `git diff --check`, strict verification of five rebuilt private PDFs, visual PDF review, citation checks, and staged privacy/security scans.

See [PROJECT_STATUS.md](PROJECT_STATUS.md) for the verification record, [HANDOFF.md](HANDOFF.md) for operating commands, and [docs/GUIA_USO_ES.md](docs/GUIA_USO_ES.md) for the complete Windows guide in Spanish.

## Documentation

- [Initial RenderCV and grounded-cv assessment](docs/01-repository-assessment-and-plan.md)
- [`career-ops` integration assessment](docs/02-career-ops-assessment.md)
- [Requirements](docs/requirements.md)
- [Profile schema](docs/profile-schema.md)
- [Research notes](docs/research.md)
- [Architecture](docs/architecture.md)
- [Decisions](docs/decisions.md)
- [Security](docs/security.md)
- [Job-search workflow](docs/job-search.md)
- [Guía completa de uso en Windows](docs/GUIA_USO_ES.md)

## Sanitized examples

The `samples/` directory contains a synthetic source register, profile, signed manifest, and a declarative example of the four requirement-fit outcomes. The examples contain no real candidate, employer, education, credential, or contact data and are exercised by `tests/test_samples.py`.

## Development

```bash
uv sync --extra dev --extra render
uv run pytest
uv run ruff check .
```

Validate a private profile:

```bash
uv run truthful-cv validate-profile \
  --profile profile/private/master-profile.yaml \
  --sources profile/private/source-register.yaml
```

Build a RenderCV YAML input from a claim-linked manifest:

```bash
uv run truthful-cv build \
  --profile profile/private/master-profile.yaml \
  --sources profile/private/source-register.yaml \
  --manifest profile/private/manifests/master.yaml \
  --output generated/master/candidate-cv.yaml
```

Render the YAML, then run the explicit PDF coverage/redline gate before copying the PDF to
`deliverables/`:

```bash
uv run rendercv render generated/master/candidate-cv.yaml \
  --pdf-path rendercv_output/candidate-cv.pdf

uv run truthful-cv verify-pdf \
  --profile profile/private/master-profile.yaml \
  --sources profile/private/source-register.yaml \
  --manifest profile/private/manifests/master.yaml \
  --pdf generated/master/rendercv_output/candidate-cv.pdf
```

`verify-pdf` reloads the approved profile and manifest, reconstructs the complete rendered
string inventory (identity and contact data, headings, labels, line text, and selected
role/education metadata), and checks the PDF text layer for both coverage and manifest
redlines. Rendering alone does not run this gate automatically.

Real career data and generated artifacts are intentionally absent from repository history.
