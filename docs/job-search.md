# Job-search workflow

## Discovery

1. Search employer career pages and reviewed ATS feeds.
2. Save the exact vacancy text, canonical URL, retrieval timestamp, and content hash under `private/job-snapshots/`.
3. Normalize the posting into explicit required, preferred, and hard-filter requirements.
4. Reject stale, inaccessible, or materially incomplete postings from automatic prioritization.

## Evidence assessment

1. Match requirement tags only to approved claims.
2. Treat professional, academic, structured-training, foundational, and learning evidence as distinct levels.
3. Record hard-filter failures separately from ordinary fit gaps.
4. Keep legal declarations, work authorization, compensation, relocation, schedule, and consent decisions for the candidate.

## Tailoring

1. Select only content whose exact reviewed line signature is approved in the private profile.
2. Require each line to reference approved claims.
3. Require role and education subjects to resolve to the correct entity kind.
4. Reject cross-subject claim attribution for subject-bound lines.
5. Preserve unresolved requirements as explicit gaps rather than stronger wording.

## Rendering and review

1. Build a private RenderCV YAML file.
2. Render with the pinned RenderCV release.
3. Verify page count, text-layer presence, required manifest text, and redline absence.
4. Inspect the rendered page images for visual defects and reading order.
5. Re-check the live vacancy URL.
6. Submit manually by default.

## Tracking

The ignored private tracker stores canonical URL, status, retrieval time, fit assessment, gaps, snapshot path, and generated artifact path. Writes use a lock plus atomic replacement so concurrent updates do not silently overwrite each other.
