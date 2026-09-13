from enum import StrEnum

from pydantic import BaseModel, Field

from truthful_cv.models import ClaimStatus
from truthful_cv.profile import Profile


class FitLevel(StrEnum):
    DEEP = "deep"
    STRONG = "strong"
    PARTIAL = "partial"
    ABSENT = "absent"


class JobRequirement(BaseModel):
    id: str = Field(pattern=r"^REQ-\d{3,}$")
    description: str = Field(min_length=1)
    required: bool = True
    tags: list[str] = Field(min_length=1)
    hard_filter: bool = False


class RequirementMatch(BaseModel):
    requirement_id: str
    level: FitLevel
    claim_ids: list[str]
    explanation: str


class FitAssessment(BaseModel):
    matches: list[RequirementMatch]
    required_coverage: float = Field(ge=0, le=1)
    hard_filter_failures: list[str] = Field(default_factory=list)


def _level_for_claims(claims: list) -> FitLevel:
    professional_subjects = {
        getattr(claim, "subject_id", None)
        for claim in claims
        if claim.category == "professional"
    }
    professional_subjects.discard(None)
    if len(professional_subjects) >= 2:
        return FitLevel.DEEP
    if any(claim.category == "professional" for claim in claims):
        return FitLevel.STRONG
    if claims:
        return FitLevel.PARTIAL
    return FitLevel.ABSENT


def assess_fit(profile: Profile, requirements: list[JobRequirement]) -> FitAssessment:
    matches: list[RequirementMatch] = []
    for requirement in requirements:
        required_tags = {tag.casefold() for tag in requirement.tags}
        claims = [
            claim
            for claim in profile.claims
            if claim.status == ClaimStatus.APPROVED
            and required_tags.intersection(tag.casefold() for tag in claim.tags)
        ]
        level = _level_for_claims(claims)
        claim_ids = sorted(claim.id for claim in claims)
        explanation = (
            f"Matched approved claims: {', '.join(claim_ids)}"
            if claim_ids
            else "No approved profile claim matches the requirement tags."
        )
        matches.append(
            RequirementMatch(
                requirement_id=requirement.id,
                level=level,
                claim_ids=claim_ids,
                explanation=explanation,
            )
        )

    weights = {
        FitLevel.DEEP: 1.0,
        FitLevel.STRONG: 1.0,
        FitLevel.PARTIAL: 0.5,
        FitLevel.ABSENT: 0.0,
    }
    required_matches = [
        match for match, requirement in zip(matches, requirements, strict=True) if requirement.required
    ]
    coverage = (
        sum(weights[match.level] for match in required_matches) / len(required_matches)
        if required_matches
        else 1.0
    )
    hard_filter_failures = [
        match.requirement_id
        for match, requirement in zip(matches, requirements, strict=True)
        if requirement.hard_filter and match.level in {FitLevel.PARTIAL, FitLevel.ABSENT}
    ]
    return FitAssessment(
        matches=matches,
        required_coverage=coverage,
        hard_filter_failures=hard_filter_failures,
    )
