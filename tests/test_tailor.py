import pytest

from truthful_cv.manifest import ContentLine, ManifestPolicyError, line_signature
from truthful_cv.matcher import JobRequirement
from truthful_cv.models import Attribution, Claim, ClaimStatus, EvidenceTier
from truthful_cv.profile import Profile
from truthful_cv.tailor import rank_lines_for_job


def make_claim(claim_id: str, tags: list[str]) -> Claim:
    return Claim(
        id=claim_id,
        statement="Approved evidence.",
        category="professional",
        tier=EvidenceTier.C,
        attribution=Attribution.INDIVIDUAL,
        status=ClaimStatus.APPROVED,
        source_ids=["SRC-001"],
        tags=tags,
    )


def test_required_requirement_ranks_matching_line_first() -> None:
    profile = Profile(
        schema_version=1,
        profile_id="example",
        identity={"preferred_name": "Example Candidate"},
        claims=[make_claim("CLM-001", ["servicenow"]), make_claim("CLM-002", ["sql"])],
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
    lines = [
        ContentLine(
            id="LINE-001",
            kind="bullet",
            subject_id="ROLE-001",
            text="Used ServiceNow.",
            claim_ids=["CLM-001"],
        ),
        ContentLine(
            id="LINE-002",
            kind="bullet",
            subject_id="ROLE-001",
            text="Completed SQL validation exercises.",
            claim_ids=["CLM-002"],
        ),
    ]
    profile.approved_line_signatures = [line_signature(line, profile) for line in lines]
    requirements = [
        JobRequirement(id="REQ-001", description="SQL", required=True, tags=["sql"]),
        JobRequirement(
            id="REQ-002", description="ServiceNow", required=False, tags=["servicenow"]
        ),
    ]

    ranked = rank_lines_for_job(profile, lines, requirements)

    assert [item.line.id for item in ranked] == ["LINE-002", "LINE-001"]
    assert ranked[0].matched_requirement_ids == ["REQ-001"]
    assert ranked[0].score > ranked[1].score


def test_tailoring_rejects_unapproved_content() -> None:
    profile = Profile(
        schema_version=1,
        profile_id="example",
        identity={"preferred_name": "Example Candidate"},
        claims=[make_claim("CLM-001", ["sql"])],
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
    lines = [
        ContentLine(
            id="LINE-001",
            kind="bullet",
            subject_id="ROLE-001",
            text="Unsupported stronger wording.",
            claim_ids=["CLM-001"],
        )
    ]

    with pytest.raises(ManifestPolicyError, match="exact content approval"):
        rank_lines_for_job(profile, lines, [])
