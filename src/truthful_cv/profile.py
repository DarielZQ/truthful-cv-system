from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, BeforeValidator, Field, model_validator

from truthful_cv.models import Claim, ClaimCategory, NonBlankStr


class ProfileIntegrityError(ValueError):
    """Raised when profile references do not resolve."""

    def __init__(self, detail: str, *, cli_message: str | None = None) -> None:
        super().__init__(detail)
        self.cli_message = cli_message or "profile integrity check failed"


class ProfileInputError(ValueError):
    """Raised when profile input has an invalid top-level shape."""

    cli_message = "input must contain a YAML mapping"


class SkillEvidenceLevel(StrEnum):
    PROFESSIONAL_RECENT = "professional_recent"
    PROFESSIONAL_LIMITED = "professional_limited"
    ACADEMIC = "academic"
    STRUCTURED_TRAINING = "structured_training"
    PERSONAL_PROJECT = "personal_project"
    FOUNDATIONAL = "foundational"
    LEARNING = "learning"
    INSUFFICIENT = "insufficient"


class Skill(BaseModel):
    name: NonBlankStr
    evidence_level: SkillEvidenceLevel
    claim_ids: list[str] = Field(default_factory=list)


def _validate_date(value: object) -> str | int:
    if isinstance(value, bool):
        raise ValueError("date must be a four-digit year or valid YYYY-MM")
    if isinstance(value, int) and 1000 <= value <= 9999:
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if len(normalized) == 7 and normalized[4] == "-":
            year, month = normalized.split("-", maxsplit=1)
            if (
                year.isdigit()
                and 1000 <= int(year) <= 9999
                and month in {f"{number:02d}" for number in range(1, 13)}
            ):
                return normalized
    raise ValueError("date must be a four-digit year or valid YYYY-MM")


DateValue = Annotated[str | int, BeforeValidator(_validate_date)]


_CLAIM_SUBJECT_KIND: dict[ClaimCategory, Literal["role", "education"] | None] = {
    ClaimCategory.PROFESSIONAL: "role",
    ClaimCategory.TRAINING: "role",
    ClaimCategory.EDUCATION: "education",
    ClaimCategory.KNOWLEDGE: None,
    ClaimCategory.LANGUAGE: None,
    ClaimCategory.CERTIFICATION: None,
}


class Contact(BaseModel):
    model_config = {"extra": "allow"}

    email: NonBlankStr | None = None
    phone: NonBlankStr | None = None
    linkedin: NonBlankStr | None = None


class Identity(BaseModel):
    model_config = {"extra": "allow"}

    preferred_name: NonBlankStr
    location: NonBlankStr | None = None
    contact: Contact = Field(default_factory=Contact)


class Source(BaseModel):
    model_config = {"extra": "allow"}

    id: NonBlankStr
    kind: NonBlankStr | None = None


class SourceRegister(BaseModel):
    model_config = {"extra": "allow"}

    schema_version: int
    sources: list[Source] = Field(default_factory=list)


class Role(BaseModel):
    model_config = {"extra": "allow"}

    id: NonBlankStr
    organization: NonBlankStr
    title: NonBlankStr
    start: DateValue
    end: DateValue
    category: Literal["professional", "structured_training"]
    location: NonBlankStr | None = None
    localized_titles: dict[str, NonBlankStr] = Field(default_factory=dict)


class Education(BaseModel):
    model_config = {"extra": "allow"}

    id: NonBlankStr
    institution: NonBlankStr
    start: DateValue | None = None
    end: DateValue | None = None
    expected_end: DateValue | None = None
    status: NonBlankStr | None = None

    @model_validator(mode="after")
    def require_end_date(self) -> "Education":
        if self.end is None and self.expected_end is None:
            raise ValueError("education requires end or expected_end")
        return self


class Profile(BaseModel):
    model_config = {"extra": "allow"}

    schema_version: int
    profile_id: NonBlankStr
    identity: Identity | None = None
    claims: list[Claim] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    roles: list[Role] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    approved_line_signatures: list[str] = Field(default_factory=list)


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ProfileInputError("input must contain a YAML mapping")
    return data


def _require_unique_ids(ids: list[str | None], label: str) -> set[str | None]:
    seen: set[str | None] = set()
    for item_id in ids:
        if item_id is not None and not isinstance(item_id, str):
            message = f"{label} ID must be a string"
            raise ProfileIntegrityError(message, cli_message=message)
        if item_id in seen:
            message = f"duplicate {label} ID"
            raise ProfileIntegrityError(
                f"{message} {item_id}",
                cli_message=message,
            )
        seen.add(item_id)
    return seen


def load_profile(profile_path: Path, source_register_path: Path) -> Profile:
    source_register = SourceRegister.model_validate(_read_yaml(source_register_path))
    profile_data = _read_yaml(profile_path)
    for field in ("claims", "roles", "education", "skills", "approved_line_signatures"):
        if field in profile_data and not isinstance(profile_data[field], list):
            message = f"{field} must be a list"
            raise ProfileIntegrityError(message, cli_message=message)
    source_ids = [source.id for source in source_register.sources]
    known_source_ids = _require_unique_ids(source_ids, "source")
    _require_unique_ids(
        [item.get("id") for item in profile_data.get("claims", []) if isinstance(item, dict)],
        "claim",
    )
    _require_unique_ids(
        [item.get("id") for item in profile_data.get("roles", []) if isinstance(item, dict)],
        "role",
    )
    _require_unique_ids(
        [
            item.get("id")
            for item in profile_data.get("education", [])
            if isinstance(item, dict)
        ],
        "education",
    )
    role_ids = {
        item.get("id") for item in profile_data.get("roles", []) if isinstance(item, dict)
    }
    education_ids = {
        item.get("id")
        for item in profile_data.get("education", [])
        if isinstance(item, dict)
    }
    known_subject_ids = role_ids | education_ids
    overlapping_subject_ids = role_ids & education_ids
    if overlapping_subject_ids:
        subject_id = sorted(overlapping_subject_ids)[0]
        raise ProfileIntegrityError(
            f"subject ID {subject_id} is used by role and education"
        )
    required_subject_fields = {
        "role": (profile_data.get("roles", []), ("id", "organization", "title", "start", "end", "category")),
        "education": (profile_data.get("education", []), ("id", "institution")),
    }
    for label, (items, required_fields) in required_subject_fields.items():
        for item in items:
            if not isinstance(item, dict):
                continue
            for field in required_fields:
                if field not in item:
                    raise ProfileIntegrityError(
                        f"{label} {item.get('id', '<unknown>')} missing required field {field}"
                    )
    identity_data = profile_data.get("identity")
    if "identity" in profile_data and (
        not isinstance(identity_data, dict) or not identity_data.get("preferred_name")
    ):
        raise ProfileIntegrityError("identity.preferred_name is required")
    profile = Profile.model_validate(profile_data)
    for claim in profile.claims:
        if claim.subject_id and claim.subject_id not in known_subject_ids:
            raise ProfileIntegrityError(
                f"claim {claim.id} references unknown subject {claim.subject_id}"
            )
        subject_kind = _CLAIM_SUBJECT_KIND[claim.category]
        if claim.subject_id and subject_kind is None:
            raise ProfileIntegrityError(
                f"{claim.category} claim {claim.id} cannot reference a subject"
            )
        if claim.subject_id and subject_kind == "education" and claim.subject_id not in education_ids:
            raise ProfileIntegrityError(
                f"education claim {claim.id} requires education subject"
            )
        if claim.subject_id and subject_kind == "role" and claim.subject_id not in role_ids:
            raise ProfileIntegrityError(f"claim {claim.id} requires role subject")
        for source_id in claim.source_ids:
            if source_id not in known_source_ids:
                raise ProfileIntegrityError(
                    f"claim {claim.id} references unknown source {source_id}"
                )
    known_claim_ids = {claim.id for claim in profile.claims}
    for skill in profile.skills:
        for claim_id in skill.claim_ids:
            if claim_id not in known_claim_ids:
                raise ProfileIntegrityError(
                    f"skill {skill.name!r} references unknown claim {claim_id}"
                )
    for field in ("identity", "roles", "education"):
        if field not in profile_data:
            raise ProfileIntegrityError(f"missing required profile field {field}")
    identity = profile_data["identity"]
    if not isinstance(identity, dict) or not identity.get("preferred_name"):
        raise ProfileIntegrityError("identity.preferred_name is required")
    return profile
