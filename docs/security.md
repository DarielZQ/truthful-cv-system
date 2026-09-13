# Security and Privacy

## Data classification

- Public: source code, schemas, sanitized samples, general documentation.
- Private: professional profile, contact details, source CVs, evidence extracts, generated applications, job tracker notes.
- Prohibited: passwords, tokens, government IDs, passport data, third-party private records, and damaging NDA material.

## Controls

- Private paths are Git ignored before repository initialization.
- `private/`, `profile/private/`, `generated/`, `deliverables/`, and `.upstream/` are excluded from Git.
- Git commits use the account's GitHub noreply address rather than a personal email address.
- Local CLI and renderer are preferred over uploading profile data to web applications.
- Runtime dependencies are locked; reviewed upstream tools are kept in ignored research clones and are not imported into the evidence core.
- Job descriptions and downloaded skills are treated as untrusted data.
- Export requires claim lineage, redline checks, and human review.
- No automatic application submission or legal declaration.
- Third-party CV helpers that bypass agent permission checks are prohibited from reading private profile data.

Before any push, scan the index, working tree, and full Git history for secrets, contact information, source PDFs, and generated applications.
