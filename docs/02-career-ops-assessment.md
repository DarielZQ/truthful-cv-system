# `career-ops` integration assessment

Research snapshot: 2026-09-11 (UTC-06:00)

Reviewed upstream commit: `7f89277409cf8fb06466fd42717fb40890d81ad0` (`main`)

## Executive decision

Do **not** make `career-ops` the source of truth for the candidate's profile, CV content, or applications. Keep the custom evidence engine as the authority, keep RenderCV as the renderer, and use selected `career-ops` ideas or isolated scanner components only after pinning and review.

The repository is a broad, local-first career-operations toolkit: job discovery, ATS-provider integrations, scoring, follow-ups, application support, and CV-generation helpers.[1][3] That outer-layer scope complements this project, but it does not replace deterministic claim-to-source lineage.

## What it provides

The documented architecture separates discovery, normalization, ranking, review, follow-up, and CV workflows.[3] Its data contract defines portable YAML/JSON records and explicit data-directory conventions.[4]

The checked package manifest declares Node.js `>=22`, uses only a small direct dependency set (`minimatch`, `playwright`, and `yaml`), and is marked `private` rather than as a published npm package.[2] The repository is MIT-licensed.[10]

At the research snapshot, GitHub reported release `career-ops-v1.32.0` and an active repository with substantial ongoing issue and pull-request traffic.[1][9] Rapid activity is useful, but it also makes a moving `main` dependency inappropriate for a factual-safety workflow.

## Local execution evidence

Commands run in the isolated clone:

```text
npm install --ignore-scripts --no-audit --no-fund
npm run lint
node test-all.mjs --quick
```

Environment:

```text
Node v24.13.0
npm 11.6.2
Windows 11 / Git Bash
```

Installation completed with six packages. Lint completed and the quick test harness ran to completion, but its final result was **8,667 passed, 5 failed, 21 warnings** (exit code `1`). Because the aggregate was not green, this snapshot is not accepted as a production dependency. The process logger retained only a rolling tail, so the five failing test names were not recoverable without another full run; this limitation is recorded rather than guessed.

## Security and privacy assessment

Positive controls exist: the security policy describes local-first handling, secret scanning, URL validation, and restrictions around application automation.[5] The provider tests visible in local execution exercise host pinning, redirect rejection, SSRF guards, malformed payload handling, pagination caps, and path-injection cases.

Important risks remain:

1. CV-generation helpers invoke an external coding agent with `--dangerously-skip-permissions`. This is unsuitable for a private evidence directory unless removed or confined to a disposable, least-privilege workspace.[2]
2. The project processes job descriptions and web content, which are untrusted inputs. Prompt injection and malicious markup must never be allowed to alter profile facts, tool permissions, or application decisions.
3. Open issue `#4085` reports a CV fact-gate markup bypass scenario.[6]
4. Open issue `#4087` reports a data-directory bypass in a follow-up API path.[7]
5. Open issue `#4081` proposes additional evidence-review guards, indicating that evidence controls are still evolving rather than settled.[8]
6. Application automation can cross into legal declarations, salary statements, work authorization, background-check consent, or irreversible submission. This project therefore keeps submission manual by default.

## Fit with the truthful-CV architecture

| Responsibility | Recommended owner | Reason |
|---|---|---|
| Career evidence and stable claim IDs | Custom `truthful_cv` core | Enforces source references, approval status, attribution, and line-level lineage. |
| Job discovery and ATS-provider adapters | Selective `career-ops` reuse or inspiration | Its provider coverage and defensive URL parsing are useful, but the code must be pinned and isolated. |
| Job tracker | Custom private tracker now | Small, auditable, and already integrated with evidence snapshots. |
| Requirement-to-claim matching | Custom `truthful_cv.matcher` | Keeps matching explainable and tied to approved claims. |
| CV rendering | RenderCV `v2.8` | Deterministic YAML-to-PDF presentation. |
| Final submission | the candidate manually | Avoids unauthorized declarations and account-risk automation. |

## Adoption plan

### Adopt now

- The conceptual separation between discovery, ranking, review, follow-up, and application stages.[3]
- Canonical URL normalization, deduplication, provider host allowlists, redirect rejection, and page caps.
- Saved vacancy snapshots with collection timestamps and hashes.

### Consider later

- Copy or adapt a **small, reviewed subset** of ATS-provider clients into a separate discovery package.
- Pin an exact upstream commit and maintain a local patch queue.
- Run scanners in a subprocess with a dedicated data directory, no profile write access, no browser login state, and no agent permissions.

### Reject for now

- Importing the repository wholesale.
- Running its CV-agent commands against the candidate's private profile.
- Tracking upstream `main` directly.
- Automatic application submission.
- Any command using `--dangerously-skip-permissions` with personal data.

## Conclusion

`career-ops` is useful as an outer operations reference and a possible future source of isolated job-board adapters. It is not accepted as the factual authority, CV generator, or autonomous applicant. The immediate workflow remains:

```text
reviewed vacancy source
  -> private timestamped snapshot
  -> custom requirement/evidence assessment
  -> claim-linked tailored manifest
  -> RenderCV PDF
  -> automated and visual verification
  -> manual application
```

## Sources

[1] https://github.com/career-ops-hq/career-ops — career-ops repository
[2] https://github.com/career-ops-hq/career-ops/blob/main/package.json — career-ops package manifest
[3] https://github.com/career-ops-hq/career-ops/blob/main/ARCHITECTURE.md — career-ops architecture
[4] https://github.com/career-ops-hq/career-ops/blob/main/DATA_CONTRACT.md — career-ops data contract
[5] https://github.com/career-ops-hq/career-ops/blob/main/.github/SECURITY.md — career-ops security policy
[6] https://github.com/career-ops-hq/career-ops/issues/4085 — CV fact-gate markup issue
[7] https://github.com/career-ops-hq/career-ops/issues/4087 — data-directory bypass issue
[8] https://github.com/career-ops-hq/career-ops/issues/4081 — evidence review guard proposal
[9] https://github.com/career-ops-hq/career-ops/releases/tag/career-ops-v1.32.0 — career-ops v1.32.0 release
[10] https://github.com/career-ops-hq/career-ops/blob/main/LICENSE — career-ops MIT license
