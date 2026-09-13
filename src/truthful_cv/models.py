from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator


NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class EvidenceTier(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class Attribution(StrEnum):
    INDIVIDUAL = "individual"
    SHARED = "shared"
    TEAM = "team"
    UNKNOWN = "unknown"


class ClaimStatus(StrEnum):
    APPROVED = "approved"
    NEEDS_CONFIRMATION = "needs_confirmation"
    REJECTED = "rejected"
    INTERNAL_ONLY = "internal_only"


class ClaimCategory(StrEnum):
    PROFESSIONAL = "professional"
    TRAINING = "training"
    KNOWLEDGE = "knowledge"
    EDUCATION = "education"
    LANGUAGE = "language"
    CERTIFICATION = "certification"


class Claim(BaseModel):
    model_config = {"extra": "allow"}

    id: str = Field(pattern=r"^CLM-\d{3,}$")
    statement: NonBlankStr
    category: ClaimCategory
    tier: EvidenceTier
    attribution: Attribution
    status: ClaimStatus
    source_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    subject_id: NonBlankStr | None = None

    @model_validator(mode="after")
    def enforce_evidence_rules(self) -> "Claim":
        if self.status == ClaimStatus.APPROVED and not self.source_ids:
            raise ValueError("approved claim must reference evidence")
        if self.status == ClaimStatus.APPROVED and self.tier == EvidenceTier.D:
            raise ValueError("Tier D claim cannot be approved")
        return self
