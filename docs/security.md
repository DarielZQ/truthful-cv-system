# Security and Privacy

## Data boundary

Public files contain source, docs, and candidate-neutral synthetic fixtures. Profiles, evidence, vacancy records, generated YAML/PDFs, and deliverables are private and Git ignored. Passwords, tokens, government IDs, passport data, third-party private records, and harmful NDA material are prohibited.

`safe_private_path(root, *parts)` resolves the private root and target, rejects absolute/traversal components, drive escapes, and symlink/reparse/junction escapes. Workflow tracker, requirements, fit report, tailored manifest, generated input/PDF, and deliverable paths use this boundary. Writes are temporary-file, flushed, and atomically replaced where applicable.

## Public vacancy retrieval boundary

- Only HTTPS is accepted: no userinfo, fragments, IP literals, non-443 ports, or downgrade.
- LinkedIn, Indeed, and Glassdoor are paste-only without DNS or transport calls. Workday and Costa Rica portals are also paste-only by default.
- Recognized Greenhouse posting URLs map to the documented read-only Job Board API GET. Recognized Lever URLs map to the documented public Postings API JSON GET.
- Arbitrary employer pages are paste-only unless an operator verifies anonymous retrieval is permitted and supplies an exact `--allow-public-host`; subdomains do not inherit permission.
- No POST, authentication, cookies, JavaScript, environment proxy, CAPTCHA bypass, or access-control evasion is implemented.
- Every A/AAAA result must be globally routable. Connections pin a validated address while TLS verifies the hostname.
- Every redirect receives manual redirect validation and a hop cap. Content types, bytes, and time are bounded.
- Authentication, rate limiting, network errors, sign-in/cookie/verify-human/Cloudflare/bot challenges, or non-credible generic pages become `paste_required`.
- JSON-LD `validThrough` is parsed relative to UTC. This is snapshot metadata, not ongoing liveness verification.
- Use public posting URLs rather than authenticated or signed links. Semantic query parameters are retained privately for posting identity, so a URL containing a session token must not be supplied; the CLI never prints stored URLs.

## Output controls

Only approved requirements and evidence reach assessment. Tags are retrieval, not proof. Exact signed source lines are subsetted without new wording. RenderCV stdout/stderr are captured and renderer failures expose only a fixed workflow error. The first render stores a SHA-256; later visual approval checks exact bytes, reruns strict verification, and hash-compares the copy. The system does not submit applications or make legal declarations.
