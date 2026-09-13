from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from truthful_cv.models import Attribution, ClaimStatus, NonBlankStr
from truthful_cv.profile import Profile


class ManifestPolicyError(ValueError):
    """Raised when outward-facing content violates evidence policy."""

    cli_message = "manifest policy check failed"


class ContentLine(BaseModel):
    id: str = Field(pattern=r"^LINE-\d{3,}$")
    kind: Literal["headline", "summary", "bullet", "skill", "education", "credential"]
    text: NonBlankStr
    claim_ids: list[str] = Field(default_factory=list)
    subject_id: NonBlankStr | None = None
    subject_ids: list[str] = Field(default_factory=list)
    label: NonBlankStr | None = None

    @model_validator(mode="after")
    def require_structural_fields(self) -> "ContentLine":
        if self.kind in {"bullet", "education"} and not self.subject_id:
            raise ValueError(f"{self.kind} requires subject_id")
        if self.kind in {"skill", "education", "credential"} and not self.label:
            raise ValueError(f"{self.kind} requires label")
        return self


class ContentManifest(BaseModel):
    schema_version: int = 1
    language: NonBlankStr
    lines: list[ContentLine]
    redlines: list[str] = Field(default_factory=list)


def load_manifest(path: Path) -> ContentManifest:
    manifest = ContentManifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    seen: set[str] = set()
    for line in manifest.lines:
        if line.id in seen:
            raise ManifestPolicyError(f"duplicate line ID {line.id}")
        seen.add(line.id)
    return manifest


_TEAM_QUALIFIERS = (
    "contributed to",
    "part of the team",
    "co-owned",
    "jointly delivered",
)


def _rendered_profile_facts(
    line: ContentLine, profile: Profile, language: str
) -> dict[str, object]:
    identity = profile.identity
    if identity is None:
        raise ManifestPolicyError("profile identity is required for export approval")
    facts: dict[str, object] = {
        "language": language,
        "identity": {
            "preferred_name": identity.preferred_name,
            "location": identity.location,
            "email": identity.contact.email,
            "phone": identity.contact.phone,
            "linkedin": identity.contact.linkedin,
        },
    }
    if line.kind == "bullet" and line.subject_id:
        role = next(role for role in profile.roles if role.id == line.subject_id)
        facts["subject"] = {
            "id": role.id,
            "organization": role.organization,
            "position": role.localized_titles.get(language, role.title),
            "location": role.location,
            "start": role.start,
            "end": role.end,
            "category": role.category,
        }
    elif line.kind == "education" and line.subject_id:
        education = next(item for item in profile.education if item.id == line.subject_id)
        facts["subject"] = {
            "id": education.id,
            "institution": education.institution,
            "start": education.start,
            "end": education.expected_end or education.end,
        }
    return facts


def line_signature(
    line: ContentLine,
    profile: Profile | None = None,
    language: str = "english",
) -> str:
    payload = {
        "kind": line.kind,
        "text": line.text,
        "claim_ids": sorted(line.claim_ids),
        "subject_id": line.subject_id,
        "subject_ids": sorted(line.subject_ids),
        "label": line.label,
    }
    if profile is not None:
        payload["rendered_profile_facts"] = _rendered_profile_facts(
            line, profile, language
        )
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def validate_manifest(
    lines: list[ContentLine],
    profile: Profile,
    *,
    require_line_approval: bool = False,
    language: str = "english",
) -> None:
    claims = {claim.id: claim for claim in profile.claims}
    role_subjects = {item.id for item in profile.roles}
    education_subjects = {item.id for item in profile.education}
    known_subjects = role_subjects | education_subjects
    for line in lines:
        declared_subjects = set(line.subject_ids)
        if line.subject_id:
            declared_subjects.add(line.subject_id)
        for subject_id in declared_subjects:
            if subject_id not in known_subjects:
                raise ManifestPolicyError(f"{line.id} references unknown subject {subject_id}")
        if line.subject_id and line.subject_id not in known_subjects:
            raise ManifestPolicyError(f"{line.id} references unknown subject {line.subject_id}")
        if line.kind == "bullet" and line.subject_id not in role_subjects:
            raise ManifestPolicyError(f"{line.id} bullet requires a role subject")
        if line.kind == "education" and line.subject_id not in education_subjects:
            raise ManifestPolicyError(f"{line.id} education requires an education subject")
        if not line.claim_ids:
            raise ManifestPolicyError(f"{line.id} must reference at least one claim")
        for claim_id in line.claim_ids:
            claim = claims.get(claim_id)
            if claim is None:
                raise ManifestPolicyError(f"{line.id} references unknown claim {claim_id}")
            if claim.status != ClaimStatus.APPROVED:
                raise ManifestPolicyError(f"claim {claim_id} is not approved")
            claim_subject = claim.subject_id
            if line.subject_id and claim_subject and claim_subject != line.subject_id:
                raise ManifestPolicyError(
                    f"{line.id} claim {claim_id} belongs to {claim_subject}, not {line.subject_id}"
                )
            if claim_subject and claim_subject not in declared_subjects:
                raise ManifestPolicyError(
                    f"{line.id} must declare subject {claim_subject} for claim {claim_id}"
                )
            if claim.attribution == Attribution.TEAM and not any(
                qualifier in line.text.casefold() for qualifier in _TEAM_QUALIFIERS
            ):
                raise ManifestPolicyError(
                    f"{line.id} requires team attribution language for claim {claim_id}"
                )
        if require_line_approval and line_signature(line, profile, language) not in set(
            profile.approved_line_signatures
        ):
            raise ManifestPolicyError(f"{line.id} does not have exact content approval")
