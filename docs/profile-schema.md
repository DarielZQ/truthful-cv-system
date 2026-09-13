# Profile Schema

This document describes the fields and checks implemented by `truthful_cv`.
Unknown fields are retained on profile, claim, identity, contact, source, role, and education
models so private source metadata can remain intact.

## Source register

The source-register YAML is a mapping with:

- `schema_version`: required integer.
- `sources`: optional list; each item requires a nonblank `id` and may include a nonblank
  `kind`.

Source IDs must be unique. Every source ID used by a claim must resolve to one registered
source.

## Profile

The profile YAML is a mapping with a required integer `schema_version`, a nonblank
`profile_id`, and these collections:

- `claims`: claim records.
- `skills`: skill records.
- `roles`: role records; the key is required by `load_profile` even when the list is empty.
- `education`: education records; the key is required by `load_profile` even when the list is
  empty.
- `approved_line_signatures`: optional SHA-256 line-signature allowlist.

`identity` is required by `load_profile` and requires a nonblank `preferred_name`. Optional
nonblank identity values are `location` and contact `email`, `phone`, and `linkedin`.

### Claims

A claim requires:

- `id` matching `CLM-` followed by at least three digits.
- A nonblank `statement`.
- A supported `category`, evidence `tier`, `attribution`, and `status`.
- Optional `source_ids`, `tags`, and nonblank `subject_id`.

Approved claims require at least one source and cannot use Tier D. Claim IDs must be unique.

### Roles and education

A role requires a nonblank `id`, `organization`, and `title`; valid `start` and `end` dates;
and category `professional` or `structured_training`. Optional `location` and localized title
values are nonblank.

An education record requires a nonblank `id` and `institution`. It must have either `end` or
`expected_end`; `start` is optional. Optional `status` is nonblank.

Dates accept an integer four-digit year from 1000 through 9999 or a `YYYY-MM` string with a
month from `01` through `12`. Surrounding whitespace on date strings is stripped. Role IDs
and education IDs must each be unique and may not overlap.

When a claim has a subject, `professional` and `training` require a role subject, `education`
requires an education subject, and `knowledge`, `language`, and `certification` reject the
subject. A supported claim may omit `subject_id`.

### Skills

A skill requires a nonblank `name` and one supported evidence level. Its optional `claim_ids`
must resolve to claims in the same profile.

## Manifest

A manifest requires a nonblank `language` and a `lines` list. Optional `redlines` are literal
strings. Each line requires a unique ID matching `LINE-` followed by at least three digits, a
supported kind, nonblank text, and claim references. Skill, education, and credential lines
require a nonblank label. Bullet and education lines require one `subject_id`.

Manifest validation requires every line to reference at least one approved claim. Declared
subjects must resolve; bullets use role subjects and education lines use education subjects.
A subject-bound claim must be declared by the line and cannot be used for another subject.
Team-attributed claims require one of the implemented attribution phrases. Export also
requires the exact line signature to appear in `approved_line_signatures`; the signature
binds the line fields, language, rendered identity/contact values, and rendered role or
education values.

## Controlled values

- Tier: `A`, `B`, `C`, `D`.
- Attribution: `individual`, `shared`, `team`, `unknown`.
- Status: `approved`, `needs_confirmation`, `rejected`, `internal_only`.
- Skill evidence: `professional_recent`, `professional_limited`, `academic`, `structured_training`, `personal_project`, `foundational`, `learning`, `insufficient`.
- Claim category: `professional`, `training`, `knowledge`, `education`, `language`, `certification`.
- Role category: `professional`, `structured_training`.
- Manifest line kind: `headline`, `summary`, `bullet`, `skill`, `education`, `credential`.
