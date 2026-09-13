import pytest
from pydantic import ValidationError

from truthful_cv.manifest import (
    ContentLine,
    ContentManifest,
    ManifestPolicyError,
    validate_manifest,
)
from truthful_cv.models import Attribution, Claim, ClaimStatus, EvidenceTier
from truthful_cv.profile import Education, Profile, Role


def profile_with(*claims: Claim) -> Profile:
    return Profile(
        schema_version=1,
        profile_id="example",
        identity={"preferred_name": "Example Candidate"},
        claims=list(claims),
        skills=[],
        roles=[
            {
                "id": "ROLE-001",
                "organization": "Example Corp",
                "title": "Technician",
                "start": 2024,
                "end": 2025,
                "category": "professional",
            }
        ],
        education=[],
    )


def claim(
    claim_id: str = "CLM-001",
    *,
    status: ClaimStatus = ClaimStatus.APPROVED,
    attribution: Attribution = Attribution.INDIVIDUAL,
    subject_id: str | None = None,
) -> Claim:
    return Claim(
        id=claim_id,
        statement="Supported a technical initiative.",
        category="professional",
        tier=EvidenceTier.C,
        attribution=attribution,
        status=status,
        source_ids=["SRC-001"],
        tags=["support"],
        subject_id=subject_id,
    )


def test_content_manifest_rejects_whitespace_only_language() -> None:
    with pytest.raises(ValidationError, match="language"):
        ContentManifest(language="   ", lines=[])


def test_content_line_rejects_whitespace_only_text() -> None:
    with pytest.raises(ValidationError, match="text"):
        ContentLine(
            id="LINE-001",
            kind="summary",
            text="   ",
            claim_ids=["CLM-001"],
        )


def test_content_line_rejects_whitespace_only_required_label() -> None:
    with pytest.raises(ValidationError, match="label"):
        ContentLine(
            id="LINE-001",
            kind="skill",
            text="Technical support",
            label="   ",
            claim_ids=["CLM-001"],
        )


def test_content_line_rejects_whitespace_only_required_subject() -> None:
    with pytest.raises(ValidationError, match="subject_id"):
        ContentLine(
            id="LINE-001",
            kind="bullet",
            text="Provided technical support.",
            subject_id="   ",
            claim_ids=["CLM-001"],
        )


def test_manifest_line_must_reference_a_claim() -> None:
    with pytest.raises(ManifestPolicyError, match="must reference at least one claim"):
        validate_manifest(
            [ContentLine(id="LINE-001", kind="bullet", subject_id="ROLE-001", text="Provided support.", claim_ids=[])],
            profile_with(claim()),
        )


def test_manifest_rejects_unapproved_claim() -> None:
    with pytest.raises(ManifestPolicyError, match="is not approved"):
        validate_manifest(
            [
                ContentLine(
                    id="LINE-001",
                    kind="bullet", subject_id="ROLE-001",
                    text="Provided support.",
                    claim_ids=["CLM-001"],
                )
            ],
            profile_with(claim(status=ClaimStatus.NEEDS_CONFIRMATION)),
        )


def test_manifest_rejects_unknown_subject_reference() -> None:
    profile = profile_with(claim())
    profile.roles = []
    with pytest.raises(ManifestPolicyError, match="unknown subject ROLE-999"):
        validate_manifest(
            [
                ContentLine(
                    id="LINE-001",
                    kind="bullet",
                    subject_id="ROLE-999",
                    text="Provided support.",
                    claim_ids=["CLM-001"],
                )
            ],
            profile,
        )


def test_manifest_rejects_education_subject_for_bullet() -> None:
    profile = profile_with(claim())
    profile.roles = []
    profile.education = [
        Education(id="EDU-001", institution="Example University", end=2025)
    ]
    with pytest.raises(ManifestPolicyError, match="bullet requires a role subject"):
        validate_manifest(
            [
                ContentLine(
                    id="LINE-001",
                    kind="bullet",
                    subject_id="EDU-001",
                    text="Provided support.",
                    claim_ids=["CLM-001"],
                )
            ],
            profile,
        )


def test_manifest_rejects_cross_subject_claim() -> None:
    profile = profile_with(claim(subject_id="ROLE-002"))
    profile.roles.append(
        Role(
            id="ROLE-002",
            organization="Other Corp",
            title="Technician",
            start=2023,
            end=2024,
            category="professional",
        )
    )
    with pytest.raises(ManifestPolicyError, match="claim CLM-001 belongs to ROLE-002"):
        validate_manifest(
            [
                ContentLine(
                    id="LINE-001",
                    kind="bullet",
                    subject_id="ROLE-001",
                    text="Provided support.",
                    claim_ids=["CLM-001"],
                )
            ],
            profile,
        )


def test_manifest_rejects_undeclared_subject_bound_claim() -> None:
    profile = profile_with(claim(subject_id="ROLE-001"))
    line = ContentLine(
        id="LINE-001",
        kind="summary",
        text="Provides technical support.",
        claim_ids=["CLM-001"],
    )

    with pytest.raises(ManifestPolicyError, match="must declare subject ROLE-001"):
        validate_manifest([line], profile)


def test_export_gate_rejects_line_without_exact_approval() -> None:
    profile = profile_with(claim(subject_id="ROLE-001"))
    line = ContentLine(
        id="LINE-001",
        kind="bullet",
        subject_id="ROLE-001",
        text="Unsupported stronger wording.",
        claim_ids=["CLM-001"],
    )

    with pytest.raises(ManifestPolicyError, match="does not have exact content approval"):
        validate_manifest([line], profile, require_line_approval=True)


def test_team_claim_requires_attribution_language() -> None:
    with pytest.raises(ManifestPolicyError, match="requires team attribution language"):
        validate_manifest(
            [
                ContentLine(
                    id="LINE-001",
                    kind="bullet", subject_id="ROLE-001",
                    text="Delivered the infrastructure initiative.",
                    claim_ids=["CLM-001"],
                )
            ],
            profile_with(claim(attribution=Attribution.TEAM)),
        )


def test_team_claim_with_qualifier_is_allowed() -> None:
    validate_manifest(
        [
            ContentLine(
                id="LINE-001",
                kind="bullet", subject_id="ROLE-001",
                text="Contributed to an infrastructure initiative.",
                claim_ids=["CLM-001"],
            )
        ],
        profile_with(claim(attribution=Attribution.TEAM)),
    )
