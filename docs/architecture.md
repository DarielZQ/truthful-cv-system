# Architecture

```text
private sources -> evidence records -> approved claims -> profile views
                                            +
job snapshot -> requirements ----------------+-> fit matrix -> content manifest
                                                          -> policy gates
                                                          -> RenderCV YAML
                                                          -> PDF/text QA
                                                          -> human approval
```

## Boundaries

- `profile/private/`: real local profile, ignored by Git.
- `profile/`: schema documentation and sanitized examples.
- `src/truthful_cv/`: deterministic models, policy checks, matching, tailoring, RenderCV adapter, PDF verification, tracker, and CLI.
- `private/job-snapshots/`: timestamped vacancy text and hashes, ignored by Git.
- `deliverables/`: final PDFs for manual application, ignored by Git.
- `generated/`: local outputs, ignored except placeholder.
- `.upstream/`: disposable inspected clones, ignored.

Model-assisted extraction may propose requirements or wording. Only deterministic policy gates may authorize export.
