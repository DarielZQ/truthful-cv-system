# Truthful CV System

[![CI](../../actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)

Private-first, evidence-based CV tailoring. A typed profile and signed exact-line content library are the factual authority; RenderCV `2.8` is only the pinned PDF adapter. The tool does not submit applications.

## Technologies

**Languages**

- **Python 3.13+** (pinned to 3.14 through `.python-version`): the whole CLI, from ingestion to verification.

**Libraries and platform**

- **Pydantic**: typed, validated models for the profile, source register, manifests, vacancies, and tracker state.
- **PyYAML**: reading and writing the YAML profile, manifests, requirement drafts, and samples.
- **RenderCV 2.8** (optional `render` extra, Typst-based): the pinned adapter that turns the generated input into a PDF.
- **pypdf**: extracts the text of the rendered PDF for strict verification (page count, red lines, exact claims).
- **filelock**: serializes writes to the application tracker so concurrent runs cannot corrupt it.
- **Greenhouse Job Board API and Lever Postings API**: read-only public GET retrieval of vacancies, implemented with the Python standard library (`http.client`, `ssl`).

**Tools**

- **uv**: Python version, virtual environment, and locked dependencies (`uv.lock`).
- **pytest**: offline test suite, including transport contracts and a sanitized RenderCV end-to-end run.
- **Ruff**: linting.
- **Hatchling**: build backend for the package.
- **GitHub Actions**: continuous integration that runs the tests and Ruff on Ubuntu for every push and pull request.

## Level-2 workflow

```bash
uv run truthful-cv vacancy ingest --url URL --private-root private [--paste-file FILE] [--title TITLE] [--employer EMPLOYER]
uv run truthful-cv vacancy approve-requirements --job JOB-001 --private-root private --approve REQ-001 REQ-002
uv run truthful-cv vacancy assess --job JOB-001 --private-root private \
  --profile profile/private/master-profile.yaml \
  --sources profile/private/source-register.yaml \
  --base-manifest private/content-library.yaml
uv run truthful-cv vacancy finalize --job JOB-001 --private-root private \
  --profile profile/private/master-profile.yaml --sources profile/private/source-register.yaml
# inspect private/generated/JOB-001/cv.pdf, then:
uv run truthful-cv vacancy finalize --job JOB-001 --private-root private \
  --profile profile/private/master-profile.yaml --sources profile/private/source-register.yaml \
  --visual-approved
```

Ingestion preserves line/list boundaries and creates auditable `needs_review` requirement drafts. Review them before approval. Personal/legal decisions default to hard filters. The extractor is deterministic and heuristic; it is not AI semantic analysis.

Assessment accepts only an `approved` job and a private, reviewed base manifest whose exact line signatures are already in the profile. It ranks those exact lines by deterministic claim-tag overlap, keeps structural headline/summary lines plus positively ranked evidence lines, and writes/binds `vacancies/JOB-###/tailored-manifest.yaml`. It does not invent or sign wording. Tag overlap is retrieval only: machine output is `absent` or `partial`; `strong`/`deep` requires an explicit human semantic override and nonblank rationale.

Finalization is two-stage. The first call requires `assessed`, verifies the hashes binding the approved requirements and vacancy-specific manifest, renders once with absolute private paths, runs strict verification, and records hashes for the generated input and PDF before returning `visual_approval_required`. A later `--visual-approved` call never rerenders: it rejects changes to the manifest, generated input, or PDF, reruns verification, copies, hash-compares, then records `finalized`. Page count is configured and verified, not guaranteed.

## Retrieval policy

- LinkedIn, Indeed, Glassdoor, Workday, and Costa Rica portals are paste-only.
- Recognized Greenhouse URLs use the documented read-only Job Board API GET.
- Recognized Lever URLs use the documented public Postings API JSON GET.
- Arbitrary employer pages are paste-only unless the operator first verifies anonymous retrieval is permitted and supplies the exact hostname with `--allow-public-host HOST`.
- Retrieval never uses POST, authentication, cookies, JavaScript, proxy environment variables, or protection bypasses. Blocked, interstitial, or non-credible pages fall back to paste.

## Privacy and development

Real profiles, sources, vacancies, generated files, and deliverables stay in Git-ignored private paths. Private artifacts are resolved beneath the private root and reject traversal and symlink/reparse escapes.

```bash
uv sync --extra dev --extra render --locked
uv run pytest -p no:cacheprovider
uv run ruff check .
uv lock --check
git diff --check
```

CI (`.github/workflows/ci.yml`) runs the same `uv sync`, pytest, and Ruff steps on `ubuntu-latest`. The suite needs no network, GPU, or private data.

See [PROJECT_STATUS.md](PROJECT_STATUS.md), [HANDOFF.md](HANDOFF.md), [architecture](docs/architecture.md), [security](docs/security.md), [job workflow](docs/job-search.md), and the [Spanish Windows guide](docs/GUIA_USO_ES.md). Sanitized examples under `samples/` are synthetic and candidate-neutral.
