import pytest

from truthful_cv.matcher import FitLevel, JobRequirement, assess_fit
from truthful_cv.models import Attribution, Claim, ClaimStatus, EvidenceTier
from truthful_cv.profile import Profile
from truthful_cv.requirements import RequirementKind, RequirementPriority, RequirementReviewStatus


def _profile(category: str = "education") -> Profile:
    claim = Claim.model_validate(
        {
            "id": "CLM-001",
            "statement": "Completed an information technology diploma.",
            "category": category,
            "tier": EvidenceTier.C,
            "attribution": Attribution.INDIVIDUAL,
            "status": ClaimStatus.APPROVED,
            "source_ids": ["SRC-001"],
            "subject_id": "EDU-001" if category == "education" else "ROLE-001",
            "tags": ["diploma", "information_technology"],
        }
    )
    return Profile(schema_version=1, profile_id="example", claims=[claim], skills=[])


def test_assessment_refuses_unreviewed_requirements() -> None:
    requirement = JobRequirement(
        id="REQ-001",
        description="IT diploma",
        source_text="IT diploma required.",
        tags=["diploma"],
        review_status=RequirementReviewStatus.NEEDS_REVIEW,
    )
    with pytest.raises(ValueError, match="approved requirements"):
        assess_fit(_profile(), [requirement])


def test_legacy_required_boolean_maps_to_priority() -> None:
    preferred = JobRequirement(id="REQ-001", description="ITIL", required=False, tags=["itil"])
    assert preferred.priority == RequirementPriority.PREFERRED
    assert preferred.required is False


def test_match_reports_retrieval_score_as_not_proof() -> None:
    requirement = JobRequirement(
        id="REQ-001",
        description="IT diploma",
        source_text="IT diploma required.",
        kind=RequirementKind.EDUCATION,
        priority=RequirementPriority.REQUIRED,
        tags=["diploma", "information_technology"],
        review_status=RequirementReviewStatus.APPROVED,
    )
    match = assess_fit(_profile(), [requirement]).matches[0]
    assert match.retrieval_score == 1.0
    assert "not proof" in match.explanation.casefold()


def test_human_override_controls_semantic_level_with_rationale() -> None:
    requirement = JobRequirement(
        id="REQ-001",
        description="IT diploma",
        source_text="IT diploma required.",
        kind=RequirementKind.EDUCATION,
        tags=["diploma"],
        hard_filter=True,
        review_status=RequirementReviewStatus.APPROVED,
        override_level=FitLevel.STRONG,
        override_rationale="The approved diploma satisfies this education filter.",
    )
    result = assess_fit(_profile(), [requirement])
    assert result.matches[0].machine_level == FitLevel.PARTIAL
    assert result.matches[0].level == FitLevel.STRONG
    assert result.hard_filter_failures == []


def test_override_without_rationale_is_rejected() -> None:
    with pytest.raises(ValueError, match="rationale"):
        JobRequirement(
            id="REQ-001",
            description="Diploma",
            tags=["diploma"],
            review_status=RequirementReviewStatus.APPROVED,
            override_level=FitLevel.STRONG,
        )
