# Architecture Decisions

## ADR-001: Custom evidence core

**Decision:** implement a small typed core inspired by grounded-cv.
**Reason:** grounded-cv has strong procedures but does not machine-enforce complete claim-to-line lineage.

## ADR-002: RenderCV adapter

**Decision:** pin RenderCV 2.8 and isolate renderer-specific YAML generation.
**Reason:** mature schema and cross-platform PDF output; no need to fork the renderer.

## ADR-003: Private profile excluded from Git

**Decision:** keep source CVs, extracts, real profile, generated applications, and logs out of Git.
**Reason:** a complete career profile is high-value personal data even in a private remote repository.

## ADR-004: TDD

**Decision:** production behaviors are implemented through RED-GREEN-REFACTOR vertical slices.
**Reason:** truthfulness gates require regression evidence, not manual confidence.
