import os
import re
from enum import StrEnum
from pathlib import Path
from tempfile import NamedTemporaryFile

import yaml
from pydantic import BaseModel, Field, field_validator


class RequirementPriority(StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    INFORMATIONAL = "informational"


class RequirementKind(StrEnum):
    CAPABILITY = "capability"
    RESPONSIBILITY = "responsibility"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    CREDENTIAL = "credential"
    LANGUAGE = "language"
    LOCATION = "location"
    WORK_AUTHORIZATION = "work_authorization"
    SCHEDULE = "schedule"
    COMPENSATION = "compensation"
    TRAVEL = "travel"
    OTHER = "other"


class RequirementReviewStatus(StrEnum):
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class RequirementDraft(BaseModel):
    id: str = Field(pattern=r"^REQ-\d{3,}$")
    description: str
    source_text: str
    priority: RequirementPriority = RequirementPriority.REQUIRED
    kind: RequirementKind = RequirementKind.OTHER
    tags: list[str] = Field(min_length=1)
    personal_decision: bool = False
    hard_filter: bool | None = None
    review_status: RequirementReviewStatus = RequirementReviewStatus.NEEDS_REVIEW
    override_level: str | None = None
    override_rationale: str | None = None

    def model_post_init(self, __context: object) -> None:
        if self.hard_filter is None:
            self.hard_filter = self.personal_decision or self.kind in {
                RequirementKind.WORK_AUTHORIZATION,
                RequirementKind.LOCATION,
                RequirementKind.SCHEDULE,
                RequirementKind.COMPENSATION,
                RequirementKind.TRAVEL,
            }

    @field_validator("description", "source_text")
    @classmethod
    def meaningful_text(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value or not any(character.isalnum() for character in value):
            raise ValueError("meaningful text is required")
        return value


def _priority(text: str, section: RequirementPriority | None) -> RequirementPriority:
    lower = text.casefold()
    if section == RequirementPriority.PREFERRED or any(token in lower for token in ("preferred", "nice to have", "deseable")):
        return RequirementPriority.PREFERRED
    if any(token in lower for token in ("must", "required", "requisito", "debe")):
        return RequirementPriority.REQUIRED
    return section or RequirementPriority.INFORMATIONAL


def _kind(text: str) -> RequirementKind:
    lower = text.casefold()
    checks = [
        (RequirementKind.WORK_AUTHORIZATION, ("authorized to work", "work authorization", "permiso de trabajo")),
        (RequirementKind.COMPENSATION, ("salary", "compensation", "salario", "crc ", "$")),
        (RequirementKind.TRAVEL, ("travel", "viajar")),
        (RequirementKind.SCHEDULE, ("shift", "schedule", "turno", "horario")),
        (RequirementKind.LANGUAGE, ("english", "spanish", "bilingual", "inglés", "español")),
        (RequirementKind.EDUCATION, ("degree", "bachelor", "diploma", "university", "licenciatura")),
        (RequirementKind.CREDENTIAL, ("certification", "certified", "certificación", "itil")),
        (RequirementKind.EXPERIENCE, ("experience", "years", "años", "experiencia")),
        (RequirementKind.LOCATION, ("location", "located", "ubicación", "reside")),
        (RequirementKind.RESPONSIBILITY, ("responsible", "responsibility", "duties", "responsabilidades")),
    ]
    for kind, tokens in checks:
        if any(token in lower for token in tokens):
            return kind
    return RequirementKind.CAPABILITY


def _tags(text: str) -> list[str]:
    stop = {"must", "have", "with", "and", "the", "for", "required", "preferred", "nice", "to", "of", "in", "a", "an", "be", "up", "per"}
    words = re.findall(r"[\w+#.-]+", text.casefold(), flags=re.UNICODE)
    tags = [word.strip(".-") for word in words if len(word.strip(".-")) > 1 and word not in stop]
    return list(dict.fromkeys(tags))[:12] or ["other"]


def _split_compound(text: str) -> list[str]:
    # Only split a simple final conjunction; retain the original source quote separately.
    match = re.match(r"^(.*?\b(?:with|using|support)\s+)([^,.;]+?)\s+and\s+([^,.;]+)([.;]?)$", text, re.I)
    if not match:
        return [text]
    prefix, left, right, punctuation = match.groups()
    return [f"{prefix}{left}{punctuation}".strip(), f"{prefix}{right}{punctuation}".strip()]


def extract_requirement_drafts(description: str) -> list[RequirementDraft]:
    drafts: list[RequirementDraft] = []
    section: RequirementPriority | None = None
    candidates = re.split(r"[\r\n]+|(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚ])", description)
    for raw in candidates:
        text = re.sub(r"^[\s•*\-]+", "", raw).strip()
        if not text:
            continue
        heading = text.casefold().rstrip(":")
        if heading in {"preferred", "preferred qualifications", "preferred requirements", "deseable", "deseables"}:
            section = RequirementPriority.PREFERRED
            continue
        if heading in {"required", "requirements", "requirements and qualifications", "requisitos", "requerido", "requerimientos"}:
            section = RequirementPriority.REQUIRED
            continue
        if heading in {"responsibilities", "responsibility", "responsabilidades", "duties"}:
            section = RequirementPriority.INFORMATIONAL
            continue
        source = text
        for part in _split_compound(text):
            kind = _kind(part)
            drafts.append(
                RequirementDraft(
                    id=f"REQ-{len(drafts) + 1:03d}",
                    description=part,
                    source_text=source,
                    priority=_priority(part, section),
                    kind=kind,
                    tags=_tags(part),
                    personal_decision=kind
                    in {
                        RequirementKind.WORK_AUTHORIZATION,
                        RequirementKind.LOCATION,
                        RequirementKind.SCHEDULE,
                        RequirementKind.COMPENSATION,
                        RequirementKind.TRAVEL,
                    },
                )
            )
    return drafts


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    name: str | None = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as temp:
            yaml.safe_dump(payload, temp, sort_keys=False, allow_unicode=True)
            temp.flush()
            os.fsync(temp.fileno())
            name = temp.name
        os.replace(name, path)
    finally:
        if name and Path(name).exists():
            Path(name).unlink()


def approve_requirements(path: Path, drafts: list[RequirementDraft], approved_ids: set[str]) -> None:
    known = {draft.id for draft in drafts}
    if not approved_ids <= known:
        raise ValueError("unknown requirement approval")
    records = [
        draft.model_copy(
            update={
                "review_status": (
                    RequirementReviewStatus.APPROVED
                    if draft.id in approved_ids
                    else RequirementReviewStatus.REJECTED
                )
            }
        )
        for draft in drafts
    ]
    _atomic_write(path, {"schema_version": 1, "requirements": [item.model_dump(mode="json") for item in records]})


def save_requirement_drafts(path: Path, drafts: list[RequirementDraft]) -> None:
    _atomic_write(path, {"schema_version": 1, "requirements": [item.model_dump(mode="json") for item in drafts]})


def load_requirements(path: Path) -> list[RequirementDraft]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("requirements"), list):
        raise ValueError("invalid requirements container")
    return [RequirementDraft.model_validate(item) for item in data["requirements"]]


def load_approved_requirements(path: Path) -> list[RequirementDraft]:
    records = load_requirements(path)
    if any(item.review_status == RequirementReviewStatus.NEEDS_REVIEW for item in records):
        raise ValueError("assessment requires approved requirements")
    approved = [item for item in records if item.review_status == RequirementReviewStatus.APPROVED]
    if not approved:
        raise ValueError("assessment requires approved requirements")
    return approved
