from pathlib import Path

import pytest
from pydantic import ValidationError

from truthful_cv.requirements import (
    RequirementDraft,
    RequirementKind,
    RequirementPriority,
    RequirementReviewStatus,
    approve_requirements,
    extract_requirement_drafts,
    load_approved_requirements,
)
from truthful_cv.vacancy import extract_posting


def test_jsonld_jobposting_is_preferred_and_scripts_are_not_retained() -> None:
    html = b'''<html><head><script type="application/ld+json">{
      "@context":"https://schema.org", "@type":"JobPosting",
      "title":"IT Support", "hiringOrganization":{"name":"Example Corp"},
      "jobLocation":{"address":{"addressLocality":"San Jose","addressCountry":"CR"}},
      "description":"<p>Provide support to users and troubleshoot Windows.</p>",
      "identifier":{"value":"EXT-42"}, "datePosted":"2026-09-10"
    }</script><script>alert('secret')</script></head><body>teaser</body></html>'''
    posting = extract_posting(html, "text/html")
    assert posting.title == "IT Support"
    assert posting.employer == "Example Corp"
    assert posting.external_id == "EXT-42"
    assert posting.description == "Provide support to users and troubleshoot Windows."
    assert "alert" not in posting.description


def test_incomplete_visible_html_requires_paste() -> None:
    with pytest.raises(ValueError, match="incomplete posting"):
        extract_posting(b"<html><body>Please log in</body></html>", "text/html")


def test_requirement_extraction_is_deterministic_auditable_and_splits_compound_bullets() -> None:
    text = """Requirements:
- Must have 2 years of experience with Windows and Active Directory.
- Fluent English required.
Preferred:
- Nice to have ITIL certification.
Schedule: Night shift.
Salary: CRC 900,000 per month.
"""
    first = extract_requirement_drafts(text)
    second = extract_requirement_drafts(text)
    assert first == second
    assert all(item.review_status == RequirementReviewStatus.NEEDS_REVIEW for item in first)
    assert any(item.priority == RequirementPriority.REQUIRED for item in first)
    assert any(item.priority == RequirementPriority.PREFERRED for item in first)
    assert {item.kind for item in first} >= {
        RequirementKind.EXPERIENCE,
        RequirementKind.LANGUAGE,
        RequirementKind.CREDENTIAL,
        RequirementKind.SCHEDULE,
        RequirementKind.COMPENSATION,
    }
    assert all(item.source_text for item in first)
    assert any("Windows" in item.description for item in first)
    assert any("Active Directory" in item.description for item in first)


def test_legal_personal_filters_are_marked_for_personal_decision() -> None:
    drafts = extract_requirement_drafts("Must be authorized to work in Costa Rica. Travel up to 20%.")
    assert any(item.kind == RequirementKind.WORK_AUTHORIZATION and item.personal_decision for item in drafts)
    assert any(item.kind == RequirementKind.TRAVEL and item.personal_decision for item in drafts)


def test_requirement_approval_is_atomic_and_loader_rejects_needs_review(tmp_path: Path) -> None:
    drafts = [
        RequirementDraft(
            id="REQ-001",
            description="Windows support",
            source_text="Must support Windows.",
            priority=RequirementPriority.REQUIRED,
            kind=RequirementKind.CAPABILITY,
            tags=["windows"],
        )
    ]
    path = tmp_path / "requirements.yaml"
    approve_requirements(path, drafts, approved_ids={"REQ-001"})
    loaded = load_approved_requirements(path)
    assert loaded[0].review_status == RequirementReviewStatus.APPROVED

    approve_requirements(path, drafts, approved_ids=set())
    with pytest.raises(ValueError, match="approved requirements"):
        load_approved_requirements(path)


def test_approved_loader_ignores_explicitly_rejected_drafts(tmp_path: Path) -> None:
    drafts = [
        RequirementDraft(
            id="REQ-001", description="Windows", source_text="Windows required.", tags=["windows"]
        ),
        RequirementDraft(
            id="REQ-002", description="Marketing", source_text="Marketing copy.", tags=["marketing"]
        ),
    ]
    path = tmp_path / "requirements.yaml"
    approve_requirements(path, drafts, {"REQ-001"})
    assert [item.id for item in load_approved_requirements(path)] == ["REQ-001"]


def test_requirement_schema_rejects_empty_source_quote() -> None:
    with pytest.raises(ValidationError):
        RequirementDraft(
            id="REQ-001", description="Windows", source_text=" ", tags=["windows"]
        )
