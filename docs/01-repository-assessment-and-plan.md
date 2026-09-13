# Truthful CV System: Repository Assessment and Implementation Plan

**Research snapshot:** 2026-09-11
**Scope:** Read-only inspection of documentation, source files, issues, releases, CI, and repository activity. No repository was cloned or installed, and no repository code was executed.

## Executive recommendation

Use **RenderCV as the rendering backend**, but do not use it as the source of truth or the personalization engine. Use the **grounded-cv methodology as a design reference**, then implement a small private, deterministic evidence layer around it. Do not fork RenderCV. Pin an upstream RenderCV release and keep the adapter thin. For grounded-cv, either vendor the specific templates/skills at a reviewed commit or make a private fork only if we want to track upstream changes.

This is preferable to installing both repositories unchanged:

1. RenderCV is a mature, focused YAML-to-PDF renderer with strict schema validation and strong cross-platform testing.[3][4][8]
2. grounded-cv directly addresses truthful personalization through evidence tiers, attribution, claims, gaps, fit scoring, constrained tailoring, and post-render checks.[10][11][12]
3. grounded-cv is only three days old at this snapshot, has no release, no adoption history, and most of its safety model is implemented as agent instructions and manual procedure rather than a machine-enforced claim-lineage engine.[17][21][22]
4. Therefore, combine their responsibilities but harden the boundary: **our evidence database and validators decide what may be said; RenderCV decides how approved content is rendered.**

## What each repository does

### RenderCV

RenderCV is a CV/resume rendering system. Its core path is:

```text
RenderCV YAML
  -> ruamel.yaml parser
  -> Pydantic validation / RenderCVModel
  -> Jinja2 templates
  -> Typst source
  -> Typst compiler
  -> PDF
```

It can also generate Typst, Markdown, HTML, and PNG outputs. Its JSON Schema and Pydantic models give useful structural validation, but they validate shape and field rules—not whether a career claim is true.[3][4]

**Best use here:** accept a generated, approved YAML document and produce consistent, professional PDFs. It should be a replaceable output adapter, not the master profile.

### grounded-cv

grounded-cv is not a conventional application or database. It is an Agent Skills framework, a collection of Markdown templates, a fictional sample profile, workflow instructions, and Python validation scripts. It explicitly depends on RenderCV for rendering.[10][11]

Its slow loop is:

```text
source material + interview
  -> career knowledge base
  -> evidence/attribution audit
  -> content map
  -> master CV
```

Its per-job loop is:

```text
job description
  -> requirement decomposition
  -> evidence-backed fit score
  -> stop if weak fit, otherwise tailor
  -> RenderCV YAML/PDF
  -> automated and manual verification
```

This matches the intended workflow closely.[14][15][16]

## Capability comparison

| Area | RenderCV | grounded-cv | Assessment |
|---|---|---|---|
| Master professional profile | CV-shaped YAML only | Markdown knowledge base with identity, facts, impact ledger, claims register, gaps, capability map, projects, and bullet library | grounded-cv is closer, but the schema is only partly machine-enforced.[13] |
| Evidence provenance | None | A/B/C/D evidence tiers, source references, and individual/shared/team attribution | Strong methodology; needs deterministic lineage validation.[12] |
| Job-description analysis | None | Agent decomposes must-haves, technologies, domain, seniority, and hard filters | Useful structured procedure, but model-judged rather than benchmarked software.[14] |
| Matching | None | Deep/Strong/Partial/Absent matrix and Strong/Good/Stretch/Weak verdict | Suitable as a starting rubric; preserve the evidence IDs used for every score.[14] |
| Tailoring | Manual YAML editing | Reorder/subset the master, swap reserve bullets, adjust only defensible headline/summary framing | Good anti-drift constraint, but enforcement is mostly instructional.[15] |
| Truthfulness enforcement | Schema correctness only | Tiers, attribution rules, gaps, redlines, content map, verifier, manual checklist | Directionally correct; current verifier cannot prove every CV line came from an allowed claim.[16][17] |
| PDF/ATS output | Primary purpose | Delegates to RenderCV and checks extracted text | Use RenderCV plus independent local verification.[5][16] |
| Application submission | None | Explicitly human-only | Correct safety boundary.[18] |

## Architecture and implementation details

### RenderCV architecture and dependencies

RenderCV 2.8 requires Python 3.12 or newer. The normal full installation adds Jinja2, Markdown, phonenumbers, Pydantic and pydantic-extra-types, ruamel.yaml, Typer, watchdog, Python Typst bindings, RenderCV fonts, and packaging. The project advertises pip, pipx, uv, and Docker installation paths.[3][6]

The repository tests Python 3.12, 3.13, and 3.14 on Ubuntu, Windows, and macOS. The inspected latest successful `main` test run passed.[8][27]

### grounded-cv architecture and dependencies

grounded-cv stores the user's material under a gitignored `workspace/`, with plain Markdown/YAML templates and six agent skills: KB build, KB audit, master build, role fit, tailoring, and verification. The only direct Python requirement in `scripts/requirements.txt` is `pyyaml>=6.0`; RenderCV is installed separately. `pdftotext` from Poppler is optional but strongly recommended because PDF text-layer checks are skipped without it.[10][17][26]

The knowledge base starts with five core files: operating rules, identity/facts, impact ledger, claims register, and gaps. Recommended additions include positioning, capability map with explicit absences, projects, and a bullet library.[13]

## Installation and Windows compatibility

### RenderCV

**Expected Windows compatibility: good.** The official test matrix includes Windows across all supported Python versions.[8] Use `uv tool install "rendercv[full]" --python 3.13` or an isolated virtual environment rather than an opaque standalone binary. A previously reported Windows locked-PDF/watch-mode problem was closed, and grounded-cv's verifier contains a stale-output safeguard for locked files.[17]

### grounded-cv

**Likely compatible, but not yet adequately demonstrated.** Its Python scripts use portable libraries such as `pathlib`, `shutil`, and `subprocess`; however, its CI runs only on Ubuntu, its optional strongest PDF verification depends on finding a Windows Poppler build, and its pre-commit hook is a POSIX shell script using `grep`. The hook should work inside Git for Windows/Git Bash but is not a native PowerShell implementation.[17][19][28]

Before using real data, a Windows-specific test matrix should cover path spaces, Unicode, CRLF, locked PDFs, missing Poppler, multiple CV variants, and non-ASCII names.

## ATS assessment

RenderCV's own ATS report tested 20 PDFs—four test resumes across five themes—using two text extractors and three commercial parsing services. It reports extractable text and successful parsing of core fields across the test set.[5]

Treat this as strong evidence of machine-readable PDFs, not a universal guarantee. ATS products differ, keyword ranking is separate from text extraction, and an open issue shows that the documentation's PDF/UA language is too broad: default output is tagged and structurally close, but RenderCV 2.8 does not explicitly request or declare PDF/UA-1 conformance.[9]

For this project, “ATS-friendly” should mean that each generated PDF passes our own repeatable checks:

- selectable, sufficiently long text layer;
- correct reading order and candidate name first;
- required contact fields and standard headings present;
- no forbidden text;
- acceptable page count;
- comparison of extracted text against the approved content manifest;
- manual visual review;
- optionally, a sampled external parser test before adopting a new theme or RenderCV version.

Use a conservative single-column theme, no photo, no information carried only by icons, and `show_top_note: false`, as grounded-cv recommends.[11][16]

## Maintenance and maturity

### RenderCV

At the snapshot, the repository reports roughly 17.5k stars, 1.35k forks, 46 open issues, and 33 open pull requests. Version 2.8 was released on 2026-03-21; the latest commit on `main` inspected was dated 2026-03-25, and that main CI run passed.[7][20][27]

Assessment: mature and broadly used, but release 2.8 has unresolved reports, including nested bullet indentation and a PDF/UA documentation/behavior discrepancy.[9][25] Pin the version, avoid nested bullets initially, test before upgrading, and do not track `main` directly.

### grounded-cv

The repository was created on 2026-09-08, has seven initial commits, zero stars/forks/open issues at this snapshot, no published GitHub release, and one successful Ubuntu CI workflow on `main`.[21][22][28]

Assessment: promising but **experimental and unproven**. Its maintenance trajectory cannot be inferred from three days of history. Use its ideas, templates, and tests only after reviewing and pinning a commit; do not make it an uncontrolled remote skill dependency.

## Security and privacy assessment

Both repositories use the MIT license, allowing private modification and integration while retaining the license notice.[1][2]

RenderCV has Dependabot configuration and CI, but neither repository's GitHub community profile exposed a SECURITY policy at inspection time.[8][23][24] A local CLI avoids sending CV contents to the RenderCV web application, but package installation still introduces normal Python/npm supply-chain risks. Pin versions, verify lockfiles/hashes where practical, and keep rendering offline.

grounded-cv protects `workspace/` with `.gitignore` and offers an opt-in pre-commit hook that rejects workspace files and common contact/ID patterns. It also recommends a separate private repository for personal data.[18] These are useful safeguards, not encryption or access control. The hook is inactive until configured, regex scans can miss data, and redlines detect configured strings only after content has already been processed by the AI agent.

Additional controls for our implementation:

- keep the real profile outside any public repository;
- encrypt the device/backup and restrict filesystem permissions;
- never store passwords, government IDs, third-party personal data, or damaging NDA material;
- store evidence metadata and hashes rather than unnecessary document copies;
- mark confidential claims and maintain safe external translations;
- treat job descriptions and downloaded skill files as untrusted input, not instructions;
- require human approval before any CV is exported or sent;
- do not automate job submission in the first implementation.

## Important limitations of grounded-cv

1. **Lineage is not fully enforced by code.** `verify.py` checks rendering success, page count, text-layer length, candidate-name ordering, contacts, literal/regex redlines, configured team metrics, and headings. It does not parse every bullet and prove that it maps to a claim ID, enforce evidence tiers, or detect every strengthened paraphrase.[16][17]
2. **The “database” is a Markdown convention.** It is readable and portable, but referential integrity and required fields are not guaranteed.
3. **Matching is an agent judgment.** There is no calibrated scoring model, benchmark, vector index, or deterministic requirement parser.
4. **Evidence tiers still require human judgment.** A file path or artifact does not prove authorship, scope, or attribution.
5. **Redline matching is finite.** Unknown secrets, paraphrases, or unlisted confidential terms can escape.
6. **No ingestion pipeline.** OCR, LinkedIn normalization, duplicate resolution, document hashing, and provenance extraction must be added.
7. **No Windows CI.** Portability is plausible, not proven.[19][28]
8. **A new upstream skill can change agent behavior.** Installing skills directly from a moving branch creates prompt/supply-chain risk; pin and review them.

## Recommended architecture

```text
                           PRIVATE / LOCAL
┌──────────────────────────────────────────────────────────────────┐
│  Source material                                                 │
│  current/old CVs, LinkedIn export, certificates, project docs,   │
│  reviews, user interview                                         │
└──────────────────────────────┬───────────────────────────────────┘
                               v
┌──────────────────────────────────────────────────────────────────┐
│  Evidence store                                                  │
│  evidence_id, source type/path/hash, owner, date, confidentiality│
└──────────────────────────────┬───────────────────────────────────┘
                               v
┌──────────────────────────────────────────────────────────────────┐
│  Canonical claim registry                                        │
│  claim_id, canonical fact, tier, attribution, dates, skills,     │
│  evidence_ids, allowed wording, forbidden wording, status        │
└───────────────────────┬──────────────────────────────────────────┘
                        │
           ┌────────────┴────────────┐
           v                         v
┌───────────────────────┐  ┌───────────────────────────────────────┐
│ Master profile views  │  │ Job description snapshot              │
│ roles/projects/skills │  │ raw text + URL/date/hash               │
└───────────┬───────────┘  └──────────────────┬────────────────────┘
            └──────────────────┬───────────────┘
                               v
┌──────────────────────────────────────────────────────────────────┐
│ Requirement extraction + fit matrix                              │
│ requirement_id -> must/nice/hard filter -> supporting claim_ids  │
│ -> Deep/Strong/Partial/Absent -> apply/stop decision              │
└──────────────────────────────┬───────────────────────────────────┘
                               v
┌──────────────────────────────────────────────────────────────────┐
│ Tailored content manifest                                        │
│ every summary sentence/bullet/skill -> claim_ids + transformation│
└──────────────────────────────┬───────────────────────────────────┘
                               v
┌──────────────────────────────────────────────────────────────────┐
│ Deterministic policy gates                                       │
│ lineage, tiers, attribution, exact facts, confidentiality, dates │
└──────────────────────────────┬───────────────────────────────────┘
                               v
┌───────────────────────┐     RenderCV adapter     ┌───────────────┐
│ Approved RenderCV YAML├─────────────────────────>│ PDF + text     │
└───────────────────────┘                          └───────┬───────┘
                                                         v
                                               ATS/redline/manual QA
```

### Core design decision

Store two representations:

- **Human-readable profile:** Markdown views inspired by grounded-cv.
- **Machine-authoritative registry:** YAML or JSON records with stable IDs and validation schemas.

The generated RenderCV YAML is an output artifact. It must never become the evidence database. Each external line should have an internal manifest entry that preserves claim IDs even though those IDs are not printed on the CV.

### Minimum claim record

```yaml
claim_id: CLM-0042
subject: project-alpha
claim: "Built the deployment validation pipeline"
tier: B
attribution: individual
status: approved
skills: [Python, CI/CD]
dates: {start: 2024-02, end: 2024-06}
evidence_ids: [EVD-0017, EVD-0021]
confidentiality: external-safe
allowed_phrasing:
  - "Built a deployment validation pipeline..."
forbidden_strengthenings:
  - "Architected the company-wide deployment platform"
last_confirmed: 2026-09-11
```

Metrics should be separate records with units, ranges, calculation method, attribution, and publication policy.

## Proposed data flow

1. **Ingest:** copy or reference user-approved source material; compute hashes; record source metadata.
2. **Extract:** propose facts and claims with citations to exact source locations. The AI may propose; it may not approve.
3. **Interview:** resolve missing dates, scope, authorship, metrics, and confidential translations with the user.
4. **Audit:** assign evidence tier and attribution; place contradictions in a claims register; leave unknowns in gaps.
5. **Build master:** create a content map where every line references approved claim IDs; generate one- and two-page master variants.
6. **Snapshot job:** preserve the exact job description, URL, collection date, and hash.
7. **Analyze job:** produce structured requirements, priority, hard filters, and keywords.
8. **Match:** map each requirement only to approved claims; report Deep/Strong/Partial/Absent and explain gaps.
9. **Decide:** stop on a weak fit or hard filter unless the user explicitly wants an exploratory draft.
10. **Tailor:** reorder/subset approved content; any new wording must carry the same claim IDs and pass a no-strengthening review.
11. **Compile:** transform the approved manifest into RenderCV YAML and render with a pinned version.
12. **Verify:** compare PDF text to the approved manifest; run redline, attribution, ATS text-layer, page, link, and visual checks.
13. **Approve/export:** user reviews the final PDF; the system does not submit applications.
14. **Learn:** approved new evidence may update the master registry; job-specific wording cannot silently rewrite it.

## Information needed from you

Start with your **current CV**. A PDF, DOCX, or text file is enough. It is a starting source, not automatically trusted as complete or perfectly accurate.

Then, in stages:

### Essential identity and constraints

- preferred name and contact fields for the CV;
- location, remote/relocation preferences, and work authorization;
- target countries/languages and one-page/two-page preferences;
- target role families and seniority;
- information that must never appear externally.

### Career facts

- employer, title, location, and start/end dates for each role;
- responsibilities versus personal contributions;
- education, certifications, licenses, languages, awards;
- projects, portfolio, GitHub, publications, presentations, or volunteering;
- technologies used, context, depth, recency, and what you have *not* used.

### Evidence and attribution

- old CVs and LinkedIn export;
- certificate files or verification URLs;
- sanitized project documents, repositories, screenshots, reviews, or awards;
- for every metric: source, calculation, whether it was individual/shared/team, and whether it may be published;
- contradictions you already know about;
- confidential terms and their safe external descriptions.

Do **not** provide passwords, API keys, national IDs, passport details, birth date, marital status, third-party personal records, or NDA material that should not be read by an AI system.[18]

## Safe implementation plan

### Phase 0 — approval and privacy boundary

- Approve this architecture and choose the private storage location.
- Decide whether evidence files are copied, referenced, or represented only by metadata/hashes.
- Define retention, backups, and redlines.

### Phase 1 — fictional-profile prototype

- Pin reviewed commits/releases.
- Create the typed claim/evidence schemas and validation tests.
- Reproduce grounded-cv's useful checks without using personal data.
- Add Windows-specific tests.
- Do not connect job boards or external AI APIs by default.

### Phase 2 — controlled installation

- Install RenderCV in an isolated environment with a pinned version.
- Install or vendor only reviewed grounded-cv files; do not follow a moving branch automatically.
- Install Poppler only from a trusted Windows package source.
- Record exact versions and dependency hashes.

### Phase 3 — private profile build

- Import your current CV and optional supporting material.
- Conduct a structured interview.
- Require your approval for every canonical claim, evidence tier, attribution, and publishability status.
- Resolve blocking gaps before generation.

### Phase 4 — generation and verification

- Generate master content maps and RenderCV YAML.
- Render one- and two-page PDFs.
- Test at least three representative job descriptions.
- Confirm that every output line maps to approved claim IDs and that unsupported requirements remain gaps.
- Perform text-layer and visual QA before use.

### Phase 5 — operational use

- For each job, snapshot -> analyze -> fit decision -> tailor -> verify -> human approval.
- Pin upgrades and run regression tests before changing RenderCV, templates, skills, or the model.
- Never auto-submit applications in the initial system.

## Decision summary

| Option | Decision |
|---|---|
| RenderCV only | **No.** Excellent renderer, but it does not solve evidence or truthful personalization. |
| grounded-cv only | **No.** It already depends on RenderCV and is too new to trust unchanged. |
| Install both unchanged | **No.** Good demo path, insufficient deterministic lineage and supply-chain control. |
| Fork both | **No.** Forking RenderCV creates unnecessary maintenance. |
| Private fork/vendor grounded-cv + upstream RenderCV | **Acceptable.** Best if we want to stay close to its Agent Skills workflow. |
| Small custom evidence engine inspired by grounded-cv + pinned RenderCV | **Recommended.** Keeps the useful method, adds enforceable lineage, and minimizes the trusted code surface. |

## Sources

[1] https://github.com/rendercv/rendercv — rendercv/rendercv GitHub repository
[2] https://github.com/kevscec/grounded-cv — kevscec/grounded-cv GitHub repository
[3] https://docs.rendercv.com/user_guide — RenderCV user guide
[4] https://docs.rendercv.com/developer_guide/understanding_rendercv — RenderCV architecture guide
[5] https://docs.rendercv.com/ats_compatibility — RenderCV ATS compatibility report
[6] https://github.com/rendercv/rendercv/blob/main/pyproject.toml — RenderCV pyproject manifest
[7] https://github.com/rendercv/rendercv/releases/tag/v2.8 — RenderCV v2.8 release
[8] https://github.com/rendercv/rendercv/blob/main/.github/workflows/test.yaml — RenderCV test workflow
[9] https://github.com/rendercv/rendercv/issues/769 — RenderCV PDF/UA issue 769
[10] https://raw.githubusercontent.com/kevscec/grounded-cv/main/README.md — grounded-cv README
[11] https://raw.githubusercontent.com/kevscec/grounded-cv/main/AGENTS.md — grounded-cv agent instructions
[12] https://raw.githubusercontent.com/kevscec/grounded-cv/main/docs/02-evidence-system.md — grounded-cv evidence system
[13] https://raw.githubusercontent.com/kevscec/grounded-cv/main/docs/03-knowledge-base.md — grounded-cv knowledge base schema
[14] https://raw.githubusercontent.com/kevscec/grounded-cv/main/skills/cv-role-fit/SKILL.md — grounded-cv role-fit skill
[15] https://raw.githubusercontent.com/kevscec/grounded-cv/main/skills/cv-tailor/SKILL.md — grounded-cv tailoring skill
[16] https://raw.githubusercontent.com/kevscec/grounded-cv/main/skills/cv-verify/SKILL.md — grounded-cv verification skill
[17] https://raw.githubusercontent.com/kevscec/grounded-cv/main/scripts/verify.py — grounded-cv verifier source
[18] https://raw.githubusercontent.com/kevscec/grounded-cv/main/docs/06-privacy.md — grounded-cv privacy guide
[19] https://github.com/kevscec/grounded-cv/blob/main/.github/workflows/ci.yml — grounded-cv CI workflow
[20] https://api.github.com/repos/rendercv/rendercv — RenderCV repository metadata API
[21] https://api.github.com/repos/kevscec/grounded-cv — grounded-cv repository metadata API
[22] https://api.github.com/repos/kevscec/grounded-cv/releases?per_page=10 — grounded-cv releases API
[23] https://api.github.com/repos/rendercv/rendercv/community/profile — RenderCV community profile API
[24] https://api.github.com/repos/kevscec/grounded-cv/community/profile — grounded-cv community profile API
[25] https://github.com/rendercv/rendercv/issues/712 — RenderCV v2.8 nested bullet issue
[26] https://raw.githubusercontent.com/kevscec/grounded-cv/main/scripts/requirements.txt — grounded-cv requirements
[27] https://github.com/rendercv/rendercv/actions/runs/23544302545 — RenderCV main CI run
[28] https://github.com/kevscec/grounded-cv/actions/runs/34255513202 — grounded-cv main CI run
