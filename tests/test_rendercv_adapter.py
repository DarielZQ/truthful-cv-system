import pytest

from truthful_cv.manifest import ContentLine, ManifestPolicyError, line_signature
from truthful_cv.models import Attribution, Claim, ClaimStatus, EvidenceTier
from truthful_cv.profile import Profile
from truthful_cv.rendercv_adapter import build_rendercv_data


def approved_claim(claim_id: str, subject_id: str | None = None) -> Claim:
    data = {
        "id": claim_id,
        "statement": "Approved evidence.",
        "category": "professional",
        "tier": EvidenceTier.C,
        "attribution": Attribution.INDIVIDUAL,
        "status": ClaimStatus.APPROVED,
        "source_ids": ["SRC-001"],
        "tags": ["support"],
    }
    if subject_id:
        data["subject_id"] = subject_id
    return Claim.model_validate(data)


def approve_lines(
    profile: Profile, lines: list[ContentLine], language: str = "english"
) -> None:
    profile.approved_line_signatures = [
        line_signature(line, profile, language) for line in lines
    ]


def test_build_rendercv_data_uses_profile_facts_and_manifest_lines() -> None:
    profile = Profile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "example",
            "identity": {
                "preferred_name": "Example Candidate",
                "location": "Costa Rica",
                "contact": {"email": "example@example.com"},
            },
            "roles": [
                {
                    "id": "ROLE-001",
                    "organization": "Example Corp",
                    "title": "Support Technician",
                    "location": "Costa Rica",
                    "start": "2025-01",
                    "end": "2025-06",
                    "category": "professional",
                }
            ],
            "claims": [
                approved_claim("CLM-001").model_dump(),
                approved_claim("CLM-002", "ROLE-001").model_dump(),
            ],
            "skills": [],
        }
    )
    lines = [
        ContentLine(
            id="LINE-001",
            kind="headline",
            text="Technical Support Specialist",
            claim_ids=["CLM-001"],
        ),
        ContentLine(
            id="LINE-002",
            kind="summary",
            text="Provides evidence-based technical support.",
            claim_ids=["CLM-001"],
        ),
        ContentLine(
            id="LINE-003",
            kind="bullet",
            text="Resolved technical support requests.",
            claim_ids=["CLM-002"],
            subject_id="ROLE-001",
        ),
        ContentLine(
            id="LINE-004",
            kind="skill",
            label="Support",
            text="Technical support",
            claim_ids=["CLM-001"],
        ),
    ]

    approve_lines(profile, lines)
    data = build_rendercv_data(profile, lines, redlines=[])

    assert data["cv"]["name"] == "Example Candidate"
    assert data["cv"]["headline"] == "Technical Support Specialist"
    assert data["cv"]["sections"]["professional_summary"] == [
        "Provides evidence-based technical support."
    ]
    experience = data["cv"]["sections"]["experience"][0]
    assert experience["company"] == "Example Corp"
    assert experience["position"] == "Support Technician"
    assert experience["highlights"] == ["Resolved technical support requests."]
    assert list(data["cv"]["sections"])[0:3] == [
        "professional_summary",
        "experience",
        "technical_skills",
    ]
    assert "claim_ids" not in str(data)


def test_structured_training_is_not_rendered_as_employment() -> None:
    profile = Profile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "example",
            "identity": {"preferred_name": "Example Candidate", "location": "Costa Rica"},
            "roles": [
                {
                    "id": "TRAIN-001",
                    "organization": "Training Provider",
                    "title": "Cloud Support Program",
                    "start": "2024-01",
                    "end": "2024-06",
                    "category": "structured_training",
                }
            ],
            "claims": [approved_claim("CLM-001", "TRAIN-001").model_dump()],
            "skills": [],
        }
    )
    lines = [
        ContentLine(
            id="LINE-001",
            kind="bullet",
            text="Practiced cloud support tasks in structured training.",
            claim_ids=["CLM-001"],
            subject_id="TRAIN-001",
        )
    ]

    approve_lines(profile, lines)
    data = build_rendercv_data(profile, lines, redlines=[])

    sections = data["cv"]["sections"]
    assert "experience" not in sections
    assert sections["structured_training"][0]["company"] == "Training Provider"


def test_skills_render_as_ats_friendly_one_line_entries() -> None:
    profile = Profile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "example",
            "identity": {"preferred_name": "Example Candidate", "location": "Costa Rica"},
            "roles": [],
            "claims": [approved_claim("CLM-001").model_dump()],
            "skills": [],
        }
    )
    lines = [
        ContentLine(
            id="LINE-001",
            kind="skill",
            label="Support",
            text="Windows, ServiceNow, Microsoft 365",
            claim_ids=["CLM-001"],
        )
    ]

    approve_lines(profile, lines)
    data = build_rendercv_data(profile, lines, redlines=[])

    assert data["cv"]["sections"]["technical_skills"] == [
        {"label": "Support", "details": "Windows, ServiceNow, Microsoft 365"}
    ]


def test_selected_education_uses_profile_dates_and_manifest_wording() -> None:
    profile = Profile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "example",
            "identity": {"preferred_name": "Example Candidate", "location": "Costa Rica"},
            "roles": [],
            "education": [
                {
                    "id": "EDU-001",
                    "institution": "Example University",
                    "start": 2024,
                    "expected_end": 2026,
                    "status": "in_progress",
                }
            ],
            "claims": [approved_claim("CLM-001", "EDU-001").model_dump()],
            "skills": [],
        }
    )
    lines = [
        ContentLine(
            id="LINE-001",
            kind="education",
            label="Bachelor's Degree",
            text="Ingeniería Informática (in progress)",
            claim_ids=["CLM-001"],
            subject_id="EDU-001",
        )
    ]

    approve_lines(profile, lines)
    data = build_rendercv_data(profile, lines, redlines=[])

    education = data["cv"]["sections"]["education"][0]
    assert education == {
        "institution": "Example University",
        "area": "Ingeniería Informática (in progress)",
        "degree": "Bachelor's Degree",
        "start_date": 2024,
        "end_date": 2026,
    }


def test_credentials_render_separately_from_certifications_by_wording() -> None:
    profile = Profile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "example",
            "identity": {"preferred_name": "Example Candidate", "location": "Costa Rica"},
            "roles": [],
            "claims": [approved_claim("CLM-001").model_dump()],
            "skills": [],
        }
    )
    lines = [
        ContentLine(
            id="LINE-001",
            kind="credential",
            label="Microsoft",
            text="Microsoft Certified: Azure Fundamentals (AZ-900), 2025",
            claim_ids=["CLM-001"],
        )
    ]

    approve_lines(profile, lines)
    data = build_rendercv_data(profile, lines, redlines=[])

    assert data["cv"]["sections"]["certifications_and_training"] == [
        {
            "label": "Microsoft",
            "details": "Microsoft Certified: Azure Fundamentals (AZ-900), 2025",
        }
    ]


def test_linkedin_url_becomes_rendercv_social_connection() -> None:
    profile = Profile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "example",
            "identity": {
                "preferred_name": "Example Candidate",
                "location": "Costa Rica",
                "contact": {"linkedin": "https://linkedin.com/in/example-candidate/"},
            },
            "roles": [],
            "claims": [approved_claim("CLM-001").model_dump()],
            "skills": [],
        }
    )
    lines = [
        ContentLine(
            id="LINE-001",
            kind="summary",
            text="Provides technical support.",
            claim_ids=["CLM-001"],
        )
    ]
    approve_lines(profile, lines)

    data = build_rendercv_data(profile, lines, redlines=[])

    assert data["cv"]["social_networks"] == [
        {"network": "LinkedIn", "username": "example-candidate"}
    ]


def test_spanish_manifest_localizes_section_and_role_titles() -> None:
    profile = Profile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "example",
            "identity": {"preferred_name": "Example Candidate", "location": "Costa Rica"},
            "roles": [
                {
                    "id": "ROLE-001",
                    "organization": "Example Corp",
                    "title": "Support Technician",
                    "localized_titles": {"spanish": "Técnico de Soporte"},
                    "start": "2025-01",
                    "end": "2025-06",
                    "category": "professional",
                }
            ],
            "claims": [approved_claim("CLM-001", "ROLE-001").model_dump()],
            "skills": [],
        }
    )
    lines = [
        ContentLine(
            id="LINE-001",
            kind="bullet",
            text="Atendió solicitudes de soporte técnico.",
            claim_ids=["CLM-001"],
            subject_id="ROLE-001",
        )
    ]

    approve_lines(profile, lines, language="spanish")
    data = build_rendercv_data(profile, lines, language="spanish", redlines=[])

    entry = data["cv"]["sections"]["experiencia"][0]
    assert entry["position"] == "Técnico de Soporte"


def test_rendercv_export_omits_unset_optional_metadata() -> None:
    profile = Profile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "example",
            "identity": {"preferred_name": "Example Candidate"},
            "roles": [
                {
                    "id": "ROLE-001",
                    "organization": "Example Corp",
                    "title": "Technician",
                    "start": 2024,
                    "end": 2025,
                    "category": "professional",
                }
            ],
            "education": [],
            "claims": [approved_claim("CLM-001", "ROLE-001").model_dump()],
            "skills": [],
        }
    )
    line = ContentLine(
        id="LINE-001",
        kind="bullet",
        text="Resolved support requests.",
        claim_ids=["CLM-001"],
        subject_id="ROLE-001",
    )
    approve_lines(profile, [line])

    data = build_rendercv_data(profile, [line], redlines=[])

    assert "location" not in data["cv"]
    assert "location" not in data["cv"]["sections"]["experience"][0]


def test_rendercv_export_rejects_approved_forbidden_literal() -> None:
    profile = Profile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "example",
            "identity": {"preferred_name": "Example Candidate"},
            "roles": [],
            "education": [],
            "claims": [approved_claim("CLM-001").model_dump()],
            "skills": [],
        }
    )
    line = ContentLine(
        id="LINE-001",
        kind="summary",
        text="Production Kuber-\nnetes experience.",
        claim_ids=["CLM-001"],
    )
    approve_lines(profile, [line])

    with pytest.raises(ManifestPolicyError, match="forbidden redline: Kubernetes"):
        build_rendercv_data(profile, [line], redlines=["Kubernetes"])


def test_rendercv_export_rejects_tampered_identity_metadata() -> None:
    profile = Profile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "example",
            "identity": {
                "preferred_name": "Approved Candidate",
                "contact": {"email": "approved@example.com"},
            },
            "roles": [],
            "education": [],
            "claims": [approved_claim("CLM-001").model_dump()],
            "skills": [],
        }
    )
    line = ContentLine(
        id="LINE-001",
        kind="summary",
        text="Provides technical support.",
        claim_ids=["CLM-001"],
    )
    approve_lines(profile, [line])
    profile.identity.contact.email = "tampered@example.com"

    with pytest.raises(ManifestPolicyError, match="exact content approval"):
        build_rendercv_data(profile, [line], redlines=[])


def test_rendercv_export_rejects_tampered_role_metadata() -> None:
    profile = Profile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "example",
            "identity": {"preferred_name": "Example Candidate"},
            "roles": [
                {
                    "id": "ROLE-001",
                    "organization": "Approved Corp",
                    "title": "Technician",
                    "start": 2024,
                    "end": 2025,
                    "category": "professional",
                }
            ],
            "education": [],
            "claims": [approved_claim("CLM-001", "ROLE-001").model_dump()],
            "skills": [],
        }
    )
    line = ContentLine(
        id="LINE-001",
        kind="bullet",
        text="Resolved support requests.",
        claim_ids=["CLM-001"],
        subject_id="ROLE-001",
    )
    approve_lines(profile, [line])
    profile.roles[0].organization = "Tampered Corp"

    with pytest.raises(ManifestPolicyError, match="exact content approval"):
        build_rendercv_data(profile, [line], redlines=[])


def test_rendercv_export_rejects_unapproved_line_signature() -> None:
    profile = Profile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "example",
            "identity": {"preferred_name": "Example Candidate"},
            "roles": [],
            "education": [],
            "claims": [approved_claim("CLM-001").model_dump()],
            "skills": [],
            "approved_line_signatures": [],
        }
    )
    lines = [
        ContentLine(
            id="LINE-001",
            kind="summary",
            text="Unsupported stronger wording.",
            claim_ids=["CLM-001"],
        )
    ]

    with pytest.raises(ManifestPolicyError, match="exact content approval"):
        build_rendercv_data(profile, lines, redlines=[])
