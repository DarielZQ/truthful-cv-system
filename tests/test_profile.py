from pathlib import Path

import pytest
from pydantic import ValidationError

from truthful_cv.profile import (
    Education,
    Profile,
    ProfileIntegrityError,
    Role,
    Skill,
    load_profile,
)


def write_yaml(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_profile_rejects_whitespace_only_profile_id() -> None:
    with pytest.raises(ValidationError, match="profile_id"):
        Profile(schema_version=1, profile_id="   ")


def test_skill_rejects_whitespace_only_name() -> None:
    with pytest.raises(ValidationError, match="name"):
        Skill(name="   ", evidence_level="foundational")


def test_role_rejects_impossible_year_month() -> None:
    with pytest.raises(ValidationError, match="valid YYYY-MM"):
        Role(
            id="ROLE-001",
            organization="Example Corp",
            title="Technician",
            start="2025-99",
            end="2026-01",
            category="professional",
        )


def test_role_rejects_year_month_before_four_digit_year_range() -> None:
    with pytest.raises(ValidationError, match="valid YYYY-MM"):
        Role(
            id="ROLE-001",
            organization="Example Corp",
            title="Technician",
            start="0999-12",
            end="2026-01",
            category="professional",
        )


@pytest.mark.parametrize("date", [2025, "2025-01", " 2025-12 "])
def test_role_accepts_supported_date_forms(date: int | str) -> None:
    role = Role(
        id="ROLE-001",
        organization="Example Corp",
        title="Technician",
        start=date,
        end=2026,
        category="professional",
    )

    assert role.start == (date.strip() if isinstance(date, str) else date)


def test_education_rejects_impossible_year_month() -> None:
    with pytest.raises(ValidationError, match="valid YYYY-MM"):
        Education(
            id="EDU-001",
            institution="Example University",
            end="2025-00",
        )


def test_load_profile_resolves_claim_and_source_references(tmp_path: Path) -> None:
    sources = write_yaml(
        tmp_path / "sources.yaml",
        """schema_version: 1
sources:
  - id: SRC-001
    kind: cv_pdf
""",
    )
    profile = write_yaml(
        tmp_path / "profile.yaml",
        """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles: []
education: []
claims:
  - id: CLM-001
    statement: Provided technical support.
    category: professional
    tier: C
    attribution: individual
    status: approved
    source_ids: [SRC-001]
    tags: [it_support]
skills:
  - name: IT support
    evidence_level: professional_recent
    claim_ids: [CLM-001]
""",
    )

    loaded = load_profile(profile, sources)

    assert loaded.profile_id == "example"
    assert loaded.claims[0].id == "CLM-001"
    assert loaded.skills[0].claim_ids == ["CLM-001"]


def test_load_profile_rejects_unknown_claim_reference(tmp_path: Path) -> None:
    sources = write_yaml(tmp_path / "sources.yaml", "schema_version: 1\nsources: []\n")
    profile = write_yaml(
        tmp_path / "profile.yaml",
        """schema_version: 1
profile_id: example
claims: []
skills:
  - name: Python
    evidence_level: foundational
    claim_ids: [CLM-999]
""",
    )

    with pytest.raises(ProfileIntegrityError, match="unknown claim CLM-999"):
        load_profile(profile, sources)


def test_load_profile_rejects_unknown_claim_subject(tmp_path: Path) -> None:
    sources = write_yaml(
        tmp_path / "sources.yaml",
        "schema_version: 1\nsources:\n  - {id: SRC-001, kind: cv_pdf}\n",
    )
    profile = write_yaml(
        tmp_path / "profile.yaml",
        """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles: []
education: []
claims:
  - id: CLM-001
    statement: Provided technical support.
    category: professional
    tier: C
    attribution: individual
    status: approved
    source_ids: [SRC-001]
    subject_id: ROLE-999
skills: []
""",
    )

    with pytest.raises(ProfileIntegrityError, match="unknown subject ROLE-999"):
        load_profile(profile, sources)


def test_load_profile_rejects_blank_claim_subject(tmp_path: Path) -> None:
    sources = write_yaml(
        tmp_path / "sources.yaml",
        "schema_version: 1\nsources:\n  - {id: SRC-001, kind: cv_pdf}\n",
    )
    profile = write_yaml(
        tmp_path / "profile.yaml",
        """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles: []
education: []
claims:
  - id: CLM-001
    statement: Provided technical support.
    category: professional
    tier: C
    attribution: individual
    status: approved
    source_ids: [SRC-001]
    subject_id: "   "
skills: []
""",
    )

    with pytest.raises(ValueError, match="subject_id"):
        load_profile(profile, sources)


def test_load_profile_rejects_claim_subject_of_wrong_kind(tmp_path: Path) -> None:
    sources = write_yaml(
        tmp_path / "sources.yaml",
        "schema_version: 1\nsources:\n  - {id: SRC-001, kind: cv_pdf}\n",
    )
    profile = write_yaml(
        tmp_path / "profile.yaml",
        """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles:
  - {id: ROLE-001, organization: Example Corp, title: Technician, start: 2024, end: 2025, category: professional}
education: []
claims:
  - id: CLM-001
    statement: Completed a program.
    category: education
    tier: C
    attribution: individual
    status: approved
    source_ids: [SRC-001]
    subject_id: ROLE-001
skills: []
""",
    )

    with pytest.raises(ProfileIntegrityError, match="education claim CLM-001 requires education subject"):
        load_profile(profile, sources)


def test_load_profile_rejects_subject_for_subjectless_claim_category(
    tmp_path: Path,
) -> None:
    sources = write_yaml(
        tmp_path / "sources.yaml",
        "schema_version: 1\nsources:\n  - {id: SRC-001, kind: cv_pdf}\n",
    )
    profile = write_yaml(
        tmp_path / "profile.yaml",
        """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles:
  - {id: ROLE-001, organization: Example Corp, title: Technician, start: 2024, end: 2025, category: professional}
education: []
claims:
  - id: CLM-001
    statement: Has foundational knowledge.
    category: knowledge
    tier: C
    attribution: individual
    status: approved
    source_ids: [SRC-001]
    subject_id: ROLE-001
skills: []
""",
    )

    with pytest.raises(
        ProfileIntegrityError, match="knowledge claim CLM-001 cannot reference a subject"
    ):
        load_profile(profile, sources)


def test_load_profile_rejects_unknown_source_reference(tmp_path: Path) -> None:
    sources = write_yaml(tmp_path / "sources.yaml", "schema_version: 1\nsources: []\n")
    profile = write_yaml(
        tmp_path / "profile.yaml",
        """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles: []
education: []
claims:
  - id: CLM-001
    statement: Provided technical support.
    category: professional
    tier: C
    attribution: individual
    status: approved
    source_ids: [SRC-999]
skills: []
""",
    )

    with pytest.raises(ProfileIntegrityError, match="unknown source SRC-999"):
        load_profile(profile, sources)


def test_load_profile_rejects_missing_renderer_fields(tmp_path: Path) -> None:
    sources = write_yaml(tmp_path / "sources.yaml", "schema_version: 1\nsources: []\n")
    profile = write_yaml(
        tmp_path / "profile.yaml",
        "schema_version: 1\nprofile_id: example\nclaims: []\nskills: []\n",
    )

    with pytest.raises(ProfileIntegrityError, match="missing required profile field identity"):
        load_profile(profile, sources)


def test_load_profile_rejects_identity_without_preferred_name(tmp_path: Path) -> None:
    sources = write_yaml(tmp_path / "sources.yaml", "schema_version: 1\nsources: []\n")
    profile = write_yaml(
        tmp_path / "profile.yaml",
        "schema_version: 1\nprofile_id: example\nidentity: {}\nroles: []\neducation: []\nclaims: []\nskills: []\n",
    )

    with pytest.raises(ProfileIntegrityError, match="identity.preferred_name is required"):
        load_profile(profile, sources)


def test_load_profile_rejects_blank_identity_contact(tmp_path: Path) -> None:
    sources = write_yaml(tmp_path / "sources.yaml", "schema_version: 1\nsources: []\n")
    profile = write_yaml(
        tmp_path / "profile.yaml",
        """schema_version: 1
profile_id: example
identity:
  preferred_name: Example Candidate
  contact: {email: "   "}
roles: []
education: []
claims: []
skills: []
""",
    )

    with pytest.raises(ValueError, match="email"):
        load_profile(profile, sources)


def test_load_profile_rejects_blank_source_id(tmp_path: Path) -> None:
    sources = write_yaml(
        tmp_path / "sources.yaml",
        "schema_version: 1\nsources:\n  - {id: \"   \", kind: cv_pdf}\n",
    )
    profile = write_yaml(
        tmp_path / "profile.yaml",
        "schema_version: 1\nprofile_id: example\nidentity: {preferred_name: Example}\nroles: []\neducation: []\nclaims: []\nskills: []\n",
    )

    with pytest.raises(ValueError, match="id"):
        load_profile(profile, sources)


def test_load_profile_rejects_duplicate_source_ids(tmp_path: Path) -> None:
    sources = write_yaml(
        tmp_path / "sources.yaml",
        "schema_version: 1\nsources:\n  - {id: SRC-001}\n  - {id: SRC-001}\n",
    )
    profile = write_yaml(
        tmp_path / "profile.yaml",
        "schema_version: 1\nprofile_id: example\nidentity: {}\nroles: []\neducation: []\nclaims: []\nskills: []\n",
    )

    with pytest.raises(ProfileIntegrityError, match="duplicate source ID SRC-001"):
        load_profile(profile, sources)


def test_load_profile_rejects_duplicate_claim_ids(tmp_path: Path) -> None:
    sources = write_yaml(
        tmp_path / "sources.yaml",
        "schema_version: 1\nsources:\n  - {id: SRC-001}\n",
    )
    claim = "{id: CLM-001, statement: Fact., category: professional, tier: C, attribution: individual, status: approved, source_ids: [SRC-001]}"
    profile = write_yaml(
        tmp_path / "profile.yaml",
        f"schema_version: 1\nprofile_id: example\nidentity: {{}}\nroles: []\neducation: []\nclaims:\n  - {claim}\n  - {claim}\nskills: []\n",
    )

    with pytest.raises(ProfileIntegrityError, match="duplicate claim ID CLM-001"):
        load_profile(profile, sources)


@pytest.mark.parametrize(
    ("collection", "item_id", "label"),
    [("roles", "ROLE-001", "role"), ("education", "EDU-001", "education")],
)
def test_load_profile_rejects_duplicate_subject_ids(
    tmp_path: Path, collection: str, item_id: str, label: str
) -> None:
    sources = write_yaml(tmp_path / "sources.yaml", "schema_version: 1\nsources: []\n")
    duplicate_items = f"\n  - id: {item_id}\n  - id: {item_id}"
    roles = duplicate_items if collection == "roles" else " []"
    education = duplicate_items if collection == "education" else " []"
    profile = write_yaml(
        tmp_path / "profile.yaml",
        f"schema_version: 1\nprofile_id: example\nidentity: {{}}\nroles:{roles}\neducation:{education}\nclaims: []\nskills: []\n",
    )

    with pytest.raises(ProfileIntegrityError, match=f"duplicate {label} ID {item_id}"):
        load_profile(profile, sources)


def test_load_profile_rejects_role_and_education_id_collision(tmp_path: Path) -> None:
    sources = write_yaml(tmp_path / "sources.yaml", "schema_version: 1\nsources: []\n")
    profile = write_yaml(
        tmp_path / "profile.yaml",
        """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles:
  - {id: SHARED-001, organization: Example Corp, title: Technician, start: 2024, end: 2025, category: professional}
education:
  - {id: SHARED-001, institution: Example University, end: 2025}
claims: []
skills: []
""",
    )

    with pytest.raises(ProfileIntegrityError, match="subject ID SHARED-001 is used by role and education"):
        load_profile(profile, sources)


def test_load_profile_rejects_blank_education_institution(tmp_path: Path) -> None:
    sources = write_yaml(tmp_path / "sources.yaml", "schema_version: 1\nsources: []\n")
    profile = write_yaml(
        tmp_path / "profile.yaml",
        """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles: []
education:
  - {id: EDU-001, institution: "   ", start: 2024, expected_end: 2026, status: in_progress}
claims: []
skills: []
""",
    )

    with pytest.raises(ValueError, match="institution"):
        load_profile(profile, sources)


def test_load_profile_rejects_education_without_end_date(tmp_path: Path) -> None:
    sources = write_yaml(tmp_path / "sources.yaml", "schema_version: 1\nsources: []\n")
    profile = write_yaml(
        tmp_path / "profile.yaml",
        """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles: []
education:
  - {id: EDU-001, institution: Example University, start: 2024}
claims: []
skills: []
""",
    )

    with pytest.raises(ValueError, match="end or expected_end"):
        load_profile(profile, sources)


def test_load_profile_rejects_unknown_role_category(tmp_path: Path) -> None:
    sources = write_yaml(tmp_path / "sources.yaml", "schema_version: 1\nsources: []\n")
    profile = write_yaml(
        tmp_path / "profile.yaml",
        """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles:
  - {id: ROLE-001, organization: Example Corp, title: Technician, start: 2024, end: 2025, category: null}
education: []
claims: []
skills: []
""",
    )

    with pytest.raises(ValueError, match="category"):
        load_profile(profile, sources)


@pytest.mark.parametrize(
    ("roles", "education", "message"),
    [
        ("[{id: ROLE-001}]", "[]", "role ROLE-001 missing required field organization"),
        ("[]", "[{id: EDU-001}]", "education EDU-001 missing required field institution"),
    ],
)
def test_load_profile_rejects_incomplete_render_subjects(
    tmp_path: Path, roles: str, education: str, message: str
) -> None:
    sources = write_yaml(tmp_path / "sources.yaml", "schema_version: 1\nsources: []\n")
    profile = write_yaml(
        tmp_path / "profile.yaml",
        f"schema_version: 1\nprofile_id: example\nidentity: {{preferred_name: Example}}\nroles: {roles}\neducation: {education}\nclaims: []\nskills: []\n",
    )

    with pytest.raises(ProfileIntegrityError, match=message):
        load_profile(profile, sources)
