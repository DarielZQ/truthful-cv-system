# Architecture

```text
URL/paste -> normalized snapshot -> reviewed requirements -> approved
signed base content library + approved evidence -> deterministic ranking
-> vacancy-bound tailored manifest -> fit report -> assessed
-> RenderCV -> strict verification -> rendered + SHA-256
-> later byte-bound visual approval -> verified copy -> finalized
```

`providers.py` recognizes exact host boundaries and maps only Greenhouse Job Board and Lever Postings URLs to documented read-only JSON APIs. `ingestion.py` enforces HTTPS, public DNS pinning, manually validated redirects, GET-only transport, limits, and exact arbitrary-host opt-in. Protected/paste-only providers never call transport.

`vacancy.py` parses recognized API payloads or credible JobPosting/visible HTML, preserves block/list boundaries, evaluates ISO `validThrough` against UTC, rejects interstitials, and stores only normalized typed fields. It does not establish live availability.

`requirements.py` creates deterministic heuristic drafts with source quotes, section priority, personal-decision and hard-filter fields. Humans approve/reject and may add reasoned semantic adjudication. `matcher.py` uses tag overlap only for retrieval: no overlap is `absent`, overlap is at most `partial`; only explicit reasoned human override can set `strong` or `deep`.

`workflow.py` enforces `requirements_review -> approved -> assessed -> rendered -> finalized`. Assessment validates a private exact-line-signed base library, deterministically keeps structural headline/summary lines and evidence lines with positive required/preferred tag scores, and writes a private vacancy-specific subset without new wording. Human review remains necessary because overlap is not semantic proof.

Finalization uses only the tracker-bound relative manifest. Render and visual approval are separate invocations bound by SHA-256; approval never rerenders. Strict verification controls configured page maximum, text coverage, and redlines. One page is not guaranteed. Application submission is not implemented.

`storage.py` centralizes resolved private-root containment for tracker-linked workflow artifacts and rejects traversal plus symlink/reparse escapes. Private profile data, snapshots, tailored manifests, fit reports, generated files, and deliverables are Git ignored.
