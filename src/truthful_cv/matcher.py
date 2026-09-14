from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from truthful_cv.models import ClaimStatus
from truthful_cv.profile import Profile
from truthful_cv.requirements import (
    RequirementKind,
    RequirementPriority,
    RequirementReviewStatus,
)


class FitLevel(StrEnum):
    DEEP = "deep"
    STRONG = "strong"
    PARTIAL = "partial"
    ABSENT = "absent"


class JobRequirement(BaseModel):
    id: str = Field(pattern=r"^REQ-\d{3,}$")
    description: str = Field(min_length=1)
    source_text: str | None = None
    priority: RequirementPriority = RequirementPriority.REQUIRED
    kind: RequirementKind = RequirementKind.OTHER
    tags: list[str] = Field(min_length=1)
    hard_filter: bool = False
    personal_decision: bool = False
    review_status: RequirementReviewStatus = RequirementReviewStatus.APPROVED
    override_level: FitLevel | None = None
    override_rationale: str | None = None

    @model_validator(mode="before")
    @classmethod
    def legacy_required(cls, data: object) -> object:
        if isinstance(data, dict) and "required" in data and "priority" not in data:
            data = dict(data)
            data["priority"] = (
                RequirementPriority.REQUIRED if data.pop("required") else RequirementPriority.PREFERRED
            )
        return data

    @model_validator(mode="after")
    def validate_override(self) -> "JobRequirement":
        if self.override_level is not None and not (self.override_rationale or "").strip():
            raise ValueError("human override requires rationale")
        if self.source_text is None:
            self.source_text = self.description
        return self

    @property
    def required(self) -> bool:
        return self.priority == RequirementPriority.REQUIRED


class RequirementMatch(BaseModel):
    requirement_id: str
    level: FitLevel
    machine_level: FitLevel
    retrieval_score: float = Field(ge=0, le=1)
    claim_ids: list[str]
    explanation: str
    override_rationale: str | None = None


class FitAssessment(BaseModel):
    matches: list[RequirementMatch]
    required_coverage: float = Field(ge=0, le=1)
    hard_filter_failures: list[str] = Field(default_factory=list)


def _level_for_claims(claims: list) -> FitLevel:
    return FitLevel.PARTIAL if claims else FitLevel.ABSENT


def assess_fit(profile: Profile, requirements: list[JobRequirement]) -> FitAssessment:
    if any(item.review_status != RequirementReviewStatus.APPROVED for item in requirements):
        raise ValueError("assessment requires approved requirements")
    matches: list[RequirementMatch] = []
    for requirement in requirements:
        required_tags = {tag.casefold() for tag in requirement.tags}
        claims = [
            claim
            for claim in profile.claims
            if claim.status == ClaimStatus.APPROVED
            and required_tags.intersection(tag.casefold() for tag in claim.tags)
        ]
        machine_level = _level_for_claims(claims)
        level = requirement.override_level or machine_level
        claim_ids = sorted(claim.id for claim in claims)
        matched_tags = {
            tag.casefold()
            for claim in claims
            for tag in claim.tags
            if tag.casefold() in required_tags
        }
        retrieval_score = len(matched_tags) / len(required_tags)
        explanation = (
            f"Tag-overlap retrieval score {retrieval_score:.2f}; this is not proof. "
            + (
                f"Matched approved claims: {', '.join(claim_ids)}."
                if claim_ids
                else "No approved profile claim has overlapping tags."
            )
        )
        matches.append(
            RequirementMatch(
                requirement_id=requirement.id,
                level=level,
                machine_level=machine_level,
                retrieval_score=retrieval_score,
                claim_ids=claim_ids,
                explanation=explanation,
                override_rationale=requirement.override_rationale,
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
