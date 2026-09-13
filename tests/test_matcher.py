from truthful_cv.matcher import FitLevel, JobRequirement, assess_fit
from truthful_cv.models import Attribution, Claim, ClaimStatus, EvidenceTier
from truthful_cv.profile import Profile


def make_claim(claim_id: str, category: str, tags: list[str], subject_id: str | None = None) -> Claim:
    data = {
        "id": claim_id,
        "statement": f"Evidence for {', '.join(tags)}.",
        "category": category,
        "tier": EvidenceTier.C,
        "attribution": Attribution.INDIVIDUAL,
        "status": ClaimStatus.APPROVED,
        "source_ids": ["SRC-001"],
        "tags": tags,
    }
    if subject_id:
        data["subject_id"] = subject_id
    return Claim.model_validate(data)


def test_professional_evidence_scores_strong_with_traceable_claims() -> None:
    profile = Profile(
        schema_version=1,
        profile_id="example",
        claims=[make_claim("CLM-001", "professional", ["servicenow"], "ROLE-001")],
        skills=[],
    )
    requirement = JobRequirement(
        id="REQ-001", description="Experience using ServiceNow", required=True, tags=["servicenow"]
    )

    result = assess_fit(profile, [requirement])

    assert result.matches[0].level == FitLevel.STRONG
    assert result.matches[0].claim_ids == ["CLM-001"]


def test_repeated_professional_evidence_scores_deep() -> None:
    profile = Profile(
        schema_version=1,
        profile_id="example",
        claims=[
            make_claim("CLM-001", "professional", ["it_support"], "ROLE-001"),
            make_claim("CLM-002", "professional", ["it_support"], "ROLE-002"),
        ],
        skills=[],
    )

    result = assess_fit(
        profile,
        [JobRequirement(id="REQ-001", description="IT support", required=True, tags=["it_support"])],
    )

    assert result.matches[0].level == FitLevel.DEEP


def test_training_only_scores_partial_and_absent_remains_absent() -> None:
    profile = Profile(
        schema_version=1,
        profile_id="example",
        claims=[make_claim("CLM-001", "training", ["sql"], "TRAIN-001")],
        skills=[],
    )
    requirements = [
        JobRequirement(id="REQ-001", description="SQL", required=True, tags=["sql"]),
        JobRequirement(id="REQ-002", description="Tableau", required=False, tags=["tableau"]),
    ]

    result = assess_fit(profile, requirements)

    assert [match.level for match in result.matches] == [FitLevel.PARTIAL, FitLevel.ABSENT]
    assert result.required_coverage == 0.5


def test_absent_hard_filter_is_reported_as_blocking() -> None:
    profile = Profile(schema_version=1, profile_id="example", claims=[], skills=[])
    assessment = assess_fit(
        profile,
        [
            JobRequirement(
                id="REQ-001",
                description="Work authorization",
                tags=["work_authorization"],
                hard_filter=True,
            )
        ],
    )

    assert assessment.hard_filter_failures == ["REQ-001"]
