from pathlib import Path
import subprocess
import sys

import pytest

from truthful_cv.cli import main
from truthful_cv.manifest import ContentLine, line_signature
from truthful_cv.profile import Profile, load_profile
from truthful_cv.verifier import VerificationResult


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from truthful_cv.cli import main; raise SystemExit(main())",
            *args,
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def _cli_args(command: str, tmp_path: Path) -> list[str]:
    args = [
        command,
        "--profile",
        str(tmp_path / "private-profile.yaml"),
        "--sources",
        str(tmp_path / "private-sources.yaml"),
    ]
    if command in {"build", "verify-pdf"}:
        args.extend(["--manifest", str(tmp_path / "private-manifest.yaml")])
    if command == "build":
        args.extend(["--output", str(tmp_path / "private-output.yaml")])
    if command == "verify-pdf":
        args.extend(["--pdf", str(tmp_path / "private-cv.pdf")])
    return args


def _write_valid_cli_support_files(tmp_path: Path) -> None:
    (tmp_path / "private-sources.yaml").write_text(
        "schema_version: 1\nsources: []\n", encoding="utf-8"
    )
    (tmp_path / "private-manifest.yaml").write_text(
        "schema_version: 1\nlanguage: english\nlines: []\n", encoding="utf-8"
    )


def _write_valid_cli_profile(tmp_path: Path) -> None:
    (tmp_path / "private-profile.yaml").write_text(
        """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles: []
education: []
claims: []
skills: []
""",
        encoding="utf-8",
    )


def test_cli_validate_profile_subprocess_rejects_list_role_id_concisely(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources.yaml"
    sources.write_text("schema_version: 1\nsources: []\n", encoding="utf-8")
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles:
  - {id: [bad], organization: Example Corp, title: Technician, start: 2025-01, end: 2026-01, category: professional}
education: []
claims: []
skills: []
""",
        encoding="utf-8",
    )

    result = _run_cli(
        "validate-profile",
        "--profile",
        str(profile),
        "--sources",
        str(sources),
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "validation error: role ID must be a string\n"
    assert "Traceback" not in result.stderr
    assert str(tmp_path) not in result.stdout + result.stderr


def test_cli_validate_profile_subprocess_reports_missing_file_without_path(
    tmp_path: Path,
) -> None:
    missing_profile = tmp_path / "private" / "missing-profile.yaml"
    missing_sources = tmp_path / "private" / "missing-sources.yaml"

    result = _run_cli(
        "validate-profile",
        "--profile",
        str(missing_profile),
        "--sources",
        str(missing_sources),
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "validation error: file not found\n"
    assert "Traceback" not in result.stderr
    assert str(tmp_path) not in result.stdout + result.stderr


def test_cli_validate_profile_subprocess_rejects_non_mapping_yaml_without_path(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources.yaml"
    sources.write_text("schema_version: 1\nsources: []\n", encoding="utf-8")
    profile = tmp_path / "private-profile.yaml"
    profile.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    result = _run_cli(
        "validate-profile",
        "--profile",
        str(profile),
        "--sources",
        str(sources),
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "validation error: input must contain a YAML mapping\n"
    assert "Traceback" not in result.stderr
    assert str(tmp_path) not in result.stdout + result.stderr


@pytest.mark.parametrize("command", ["validate-profile", "build", "verify-pdf"])
def test_cli_subprocess_rejects_malformed_yaml_concisely(
    command: str, tmp_path: Path
) -> None:
    _write_valid_cli_support_files(tmp_path)
    (tmp_path / "private-profile.yaml").write_text(
        "identity: {preferred_name: Example Candidate\n", encoding="utf-8"
    )

    result = _run_cli(*_cli_args(command, tmp_path))

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "validation error: invalid YAML\n"
    assert "Traceback" not in result.stderr
    assert str(tmp_path) not in result.stdout + result.stderr


@pytest.mark.parametrize("command", ["validate-profile", "build", "verify-pdf"])
def test_cli_subprocess_rejects_non_mapping_yaml_concisely_across_commands(
    command: str, tmp_path: Path
) -> None:
    _write_valid_cli_support_files(tmp_path)
    (tmp_path / "private-profile.yaml").write_text(
        "- not\n- a\n- mapping\n", encoding="utf-8"
    )

    result = _run_cli(*_cli_args(command, tmp_path))

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "validation error: input must contain a YAML mapping\n"
    assert "Traceback" not in result.stderr
    assert str(tmp_path) not in result.stdout + result.stderr


@pytest.mark.parametrize("command", ["validate-profile", "build", "verify-pdf"])
@pytest.mark.parametrize("field", ["claims", "roles", "education"])
@pytest.mark.parametrize("container_text", ["null", "{}"])
def test_cli_subprocess_rejects_malformed_profile_collections_concisely(
    command: str, field: str, container_text: str, tmp_path: Path
) -> None:
    _write_valid_cli_support_files(tmp_path)
    profile = {
        "claims": "[]",
        "roles": "[]",
        "education": "[]",
    }
    profile[field] = container_text
    (tmp_path / "private-profile.yaml").write_text(
        f"""schema_version: 1
profile_id: example
identity: {{preferred_name: Example Candidate}}
roles: {profile['roles']}
education: {profile['education']}
claims: {profile['claims']}
skills: []
""",
        encoding="utf-8",
    )

    result = _run_cli(*_cli_args(command, tmp_path))

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.startswith("validation error: ")
    assert "Traceback" not in result.stderr
    assert str(tmp_path) not in result.stdout + result.stderr


@pytest.mark.parametrize("command", ["validate-profile", "build", "verify-pdf"])
def test_cli_subprocess_reports_missing_files_concisely_across_commands(
    command: str, tmp_path: Path
) -> None:
    result = _run_cli(*_cli_args(command, tmp_path))

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "validation error: file not found\n"
    assert "Traceback" not in result.stderr
    assert str(tmp_path) not in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("command", "missing_name", "expected_stdout", "expected_stderr"),
    [
        (
            "validate-profile",
            "private-profile.yaml",
            "",
            "validation error: file not found\n",
        ),
        ("build", "private-manifest.yaml", "", "validation error: file not found\n"),
        ("verify-pdf", "private-cv.pdf", "unable to read PDF\n", ""),
    ],
)
def test_cli_subprocess_reports_command_specific_missing_file_without_path(
    command: str,
    missing_name: str,
    expected_stdout: str,
    expected_stderr: str,
    tmp_path: Path,
) -> None:
    _write_valid_cli_support_files(tmp_path)
    _write_valid_cli_profile(tmp_path)
    if command == "verify-pdf":
        sources = tmp_path / "private-sources.yaml"
        sources.write_text(
            "schema_version: 1\nsources:\n  - {id: SRC-001}\n", encoding="utf-8"
        )
        profile = tmp_path / "private-profile.yaml"
        profile.write_text(
            """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles: []
education: []
claims:
  - id: CLM-001
    statement: Supported users.
    category: professional
    tier: C
    attribution: individual
    status: approved
    source_ids: [SRC-001]
skills: []
""",
            encoding="utf-8",
        )
        line = ContentLine(
            id="LINE-001",
            kind="summary",
            text="Supported users.",
            claim_ids=["CLM-001"],
        )
        signature = line_signature(line, load_profile(profile, sources), "english")
        profile.write_text(
            profile.read_text(encoding="utf-8")
            + f'approved_line_signatures: ["{signature}"]\n',
            encoding="utf-8",
        )
        (tmp_path / "private-manifest.yaml").write_text(
            """schema_version: 1
language: english
lines:
  - {id: LINE-001, kind: summary, text: Supported users., claim_ids: [CLM-001]}
""",
            encoding="utf-8",
        )
    missing_path = tmp_path / missing_name
    if missing_path.exists():
        missing_path.unlink()

    result = _run_cli(*_cli_args(command, tmp_path))

    assert result.returncode == 1
    assert result.stdout == expected_stdout
    assert result.stderr == expected_stderr
    assert "Traceback" not in result.stderr
    assert str(tmp_path) not in result.stdout + result.stderr


@pytest.mark.parametrize("command", ["validate-profile", "build", "verify-pdf"])
@pytest.mark.parametrize(
    ("sources_text", "profile_text", "expected_error"),
    [
        pytest.param(
            "schema_version: 1\nsources:\n  - {id: [bad]}\n",
            """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles: []
education: []
claims: []
skills: []
""",
            "sources.0.id:",
            id="source",
        ),
        pytest.param(
            "schema_version: 1\nsources: []\n",
            """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles: []
education: []
claims:
  - {id: [bad]}
skills: []
""",
            "claim ID must be a string",
            id="claim",
        ),
        pytest.param(
            "schema_version: 1\nsources: []\n",
            """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles:
  - {id: [bad]}
education: []
claims: []
skills: []
""",
            "role ID must be a string",
            id="role",
        ),
        pytest.param(
            "schema_version: 1\nsources: []\n",
            """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles: []
education:
  - {id: [bad]}
claims: []
skills: []
""",
            "education ID must be a string",
            id="education",
        ),
    ],
)
def test_cli_subprocess_rejects_list_ids_concisely_across_commands(
    command: str,
    sources_text: str,
    profile_text: str,
    expected_error: str,
    tmp_path: Path,
) -> None:
    (tmp_path / "private-sources.yaml").write_text(sources_text, encoding="utf-8")
    (tmp_path / "private-profile.yaml").write_text(profile_text, encoding="utf-8")
    (tmp_path / "private-manifest.yaml").write_text(
        "schema_version: 1\nlanguage: english\nlines: []\n", encoding="utf-8"
    )

    result = _run_cli(*_cli_args(command, tmp_path))

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.startswith("validation error: ")
    assert expected_error in result.stderr
    assert "Traceback" not in result.stderr
    assert str(tmp_path) not in result.stdout + result.stderr


def test_cli_validate_profile_sanitizes_path_shaped_duplicate_id(
    tmp_path: Path,
) -> None:
    secret_path = str(tmp_path / "private" / "attacker-controlled")
    (tmp_path / "private-sources.yaml").write_text(
        "schema_version: 1\nsources: []\n", encoding="utf-8"
    )
    (tmp_path / "private-profile.yaml").write_text(
        f"""schema_version: 1
profile_id: example
identity: {{preferred_name: Example Candidate}}
roles: []
education: []
claims:
  - {{id: {secret_path!r}}}
  - {{id: {secret_path!r}}}
skills: []
""",
        encoding="utf-8",
    )

    result = _run_cli(*_cli_args("validate-profile", tmp_path))

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "validation error: duplicate claim ID\n"
    assert secret_path not in result.stderr
    assert str(tmp_path) not in result.stderr


def test_cli_build_sanitizes_path_shaped_duplicate_id(tmp_path: Path) -> None:
    secret_path = str(tmp_path / "private" / "attacker-controlled")
    _write_valid_cli_support_files(tmp_path)
    (tmp_path / "private-profile.yaml").write_text(
        f"""schema_version: 1
profile_id: example
identity: {{preferred_name: Example Candidate}}
roles: []
education: []
claims:
  - {{id: {secret_path!r}}}
  - {{id: {secret_path!r}}}
skills: []
""",
        encoding="utf-8",
    )

    result = _run_cli(*_cli_args("build", tmp_path))

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "validation error: duplicate claim ID\n"
    assert secret_path not in result.stderr
    assert str(tmp_path) not in result.stderr


def test_cli_verify_pdf_sanitizes_path_shaped_duplicate_id(tmp_path: Path) -> None:
    secret_path = str(tmp_path / "private" / "attacker-controlled")
    _write_valid_cli_support_files(tmp_path)
    (tmp_path / "private-profile.yaml").write_text(
        f"""schema_version: 1
profile_id: example
identity: {{preferred_name: Example Candidate}}
roles: []
education: []
claims:
  - {{id: {secret_path!r}}}
  - {{id: {secret_path!r}}}
skills: []
""",
        encoding="utf-8",
    )

    result = _run_cli(*_cli_args("verify-pdf", tmp_path))

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "validation error: duplicate claim ID\n"
    assert secret_path not in result.stderr
    assert str(tmp_path) not in result.stderr


def test_cli_validate_profile_propagates_unexpected_value_error(monkeypatch) -> None:
    def fail(*_args) -> None:
        raise ValueError("programmer defect")

    monkeypatch.setattr("truthful_cv.cli.load_profile", fail)

    with pytest.raises(ValueError, match="programmer defect"):
        main(
            [
                "validate-profile",
                "--profile",
                "profile.yaml",
                "--sources",
                "sources.yaml",
            ]
        )


def test_cli_build_propagates_unexpected_value_error(monkeypatch) -> None:
    def fail(*_args) -> None:
        raise ValueError("programmer defect")

    monkeypatch.setattr("truthful_cv.cli.build_yaml_file", fail)

    with pytest.raises(ValueError, match="programmer defect"):
        main(
            [
                "build",
                "--profile",
                "profile.yaml",
                "--sources",
                "sources.yaml",
                "--manifest",
                "manifest.yaml",
                "--output",
                "output.yaml",
            ]
        )


def test_cli_verify_pdf_propagates_unexpected_value_error(monkeypatch) -> None:
    class ManifestStub:
        lines: list[object] = []
        language = "english"
        redlines: list[str] = []

    def fail(*_args, **_kwargs) -> None:
        raise ValueError("programmer defect")

    monkeypatch.setattr("truthful_cv.cli.load_profile", lambda *_args: object())
    monkeypatch.setattr("truthful_cv.cli.load_manifest", lambda *_args: ManifestStub())
    monkeypatch.setattr("truthful_cv.cli.build_rendercv_data", lambda *_args, **_kwargs: {})
    monkeypatch.setattr("truthful_cv.cli.rendered_string_inventory", lambda *_args: [])
    monkeypatch.setattr("truthful_cv.cli.verify_pdf", fail)

    with pytest.raises(ValueError, match="programmer defect"):
        main(
            [
                "verify-pdf",
                "--profile",
                "profile.yaml",
                "--sources",
                "sources.yaml",
                "--manifest",
                "manifest.yaml",
                "--pdf",
                "cv.pdf",
            ]
        )


def test_cli_validate_profile_reports_counts(tmp_path: Path, capsys) -> None:
    sources = tmp_path / "sources.yaml"
    sources.write_text(
        "schema_version: 1\nsources:\n  - {id: SRC-001, type: cv}\n",
        encoding="utf-8",
    )
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles: []
education: []
claims:
  - id: CLM-001
    statement: Supported users.
    category: professional
    tier: C
    attribution: individual
    status: approved
    source_ids: [SRC-001]
skills: []
""",
        encoding="utf-8",
    )

    code = main(
        [
            "validate-profile",
            "--profile",
            str(profile),
            "--sources",
            str(sources),
        ]
    )

    assert code == 0
    assert "example: 1 claims, 0 skills" in capsys.readouterr().out


def test_cli_build_writes_rendercv_yaml(tmp_path: Path) -> None:
    sources = tmp_path / "sources.yaml"
    sources.write_text(
        "schema_version: 1\nsources:\n  - {id: SRC-001, type: cv}\n",
        encoding="utf-8",
    )
    line = ContentLine(
        id="LINE-001",
        kind="summary",
        text="Supported users.",
        claim_ids=["CLM-001"],
    )
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate, location: Costa Rica}
roles: []
education: []
claims:
  - id: CLM-001
    statement: Supported users.
    category: professional
    tier: C
    attribution: individual
    status: approved
    source_ids: [SRC-001]
skills: []
""",
        encoding="utf-8",
    )
    signature = line_signature(line, load_profile(profile, sources), "english")
    profile.write_text(
        profile.read_text(encoding="utf-8")
        + f'approved_line_signatures: ["{signature}"]\n',
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        """schema_version: 1
language: english
lines:
  - {id: LINE-001, kind: summary, text: Supported users., claim_ids: [CLM-001]}
""",
        encoding="utf-8",
    )
    output = tmp_path / "cv.yaml"

    code = main(
        [
            "build",
            "--profile",
            str(profile),
            "--sources",
            str(sources),
            "--manifest",
            str(manifest),
            "--output",
            str(output),
        ]
    )

    assert code == 0
    assert output.exists()


def test_cli_verify_pdf_reports_malformed_profile_without_traceback(
    tmp_path: Path, capsys
) -> None:
    sources = tmp_path / "sources.yaml"
    sources.write_text("schema_version: 1\nsources: []\n", encoding="utf-8")
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles:
  - {id: ROLE-001, organization: Example Corp, title: Technician, start: 2025-99, end: 2026-01, category: professional}
education: []
claims: []
skills: []
""",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "schema_version: 1\nlanguage: english\nlines: []\n", encoding="utf-8"
    )

    code = main(
        [
            "verify-pdf",
            "--profile",
            str(profile),
            "--sources",
            str(sources),
            "--manifest",
            str(manifest),
            "--pdf",
            str(tmp_path / "cv.pdf"),
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "validation error:" in captured.err
    assert "valid YYYY-MM" in captured.err
    assert "Traceback" not in captured.err


def test_cli_verify_pdf_reports_malformed_profile_structure_without_traceback(
    tmp_path: Path, capsys
) -> None:
    sources = tmp_path / "sources.yaml"
    sources.write_text("schema_version: 1\nsources: []\n", encoding="utf-8")
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        "schema_version: 1\nprofile_id: example\nidentity: {preferred_name: Example}\nroles: [42]\neducation: []\nclaims: []\nskills: []\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "schema_version: 1\nlanguage: english\nlines: []\n", encoding="utf-8"
    )

    code = main(
        [
            "verify-pdf",
            "--profile",
            str(profile),
            "--sources",
            str(sources),
            "--manifest",
            str(manifest),
            "--pdf",
            str(tmp_path / "cv.pdf"),
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "validation error:" in captured.err
    assert "Traceback" not in captured.err


def test_cli_verify_pdf_rejects_unhashable_role_id_without_traceback(
    tmp_path: Path, capsys
) -> None:
    sources = tmp_path / "sources.yaml"
    sources.write_text("schema_version: 1\nsources: []\n", encoding="utf-8")
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        """schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles:
  - {id: [bad], organization: Example Corp, title: Technician, start: 2025-01, end: 2026-01, category: professional}
education: []
claims: []
skills: []
""",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "schema_version: 1\nlanguage: english\nlines: []\n", encoding="utf-8"
    )

    code = main(
        [
            "verify-pdf",
            "--profile",
            str(profile),
            "--sources",
            str(sources),
            "--manifest",
            str(manifest),
            "--pdf",
            str(tmp_path / "cv.pdf"),
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert captured.err == "validation error: role ID must be a string\n"
    assert "Traceback" not in captured.err
    assert str(tmp_path) not in captured.err


def test_cli_verify_pdf_wires_complete_inventory_and_redlines(
    tmp_path: Path, monkeypatch
) -> None:
    sources = tmp_path / "sources.yaml"
    sources.write_text(
        "schema_version: 1\nsources:\n  - {id: SRC-001, kind: cv_pdf}\n",
        encoding="utf-8",
    )
    profile_data = {
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
                "title": "Technician",
                "location": "Costa Rica",
                "start": 2024,
                "end": 2025,
                "category": "professional",
            }
        ],
        "education": [],
        "claims": [
            {
                "id": "CLM-001",
                "statement": "Supported users.",
                "category": "professional",
                "tier": "C",
                "attribution": "individual",
                "status": "approved",
                "source_ids": ["SRC-001"],
                "subject_id": "ROLE-001",
            }
        ],
        "skills": [],
    }
    profile_model = Profile.model_validate(profile_data)
    line = ContentLine(
        id="LINE-001",
        kind="bullet",
        text="Supported users.",
        claim_ids=["CLM-001"],
        subject_id="ROLE-001",
    )
    profile_data["approved_line_signatures"] = [
        line_signature(line, profile_model, "english")
    ]
    profile = tmp_path / "profile.yaml"
    import yaml

    profile.write_text(yaml.safe_dump(profile_data), encoding="utf-8")
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        """schema_version: 1
language: english
redlines: [Forbidden Phrase]
lines:
  - {id: LINE-001, kind: bullet, text: Supported users., claim_ids: [CLM-001], subject_id: ROLE-001}
""",
        encoding="utf-8",
    )
    captured = {}

    def fake_verify_pdf(pdf_path, redlines, required_texts):
        captured.update(
            pdf_path=pdf_path,
            redlines=redlines,
            required_texts=required_texts,
        )
        return VerificationResult(ok=True, redline_hits=[], errors=[])

    monkeypatch.setattr("truthful_cv.cli.verify_pdf", fake_verify_pdf)

    code = main(
        [
            "verify-pdf",
            "--profile",
            str(profile),
            "--sources",
            str(sources),
            "--manifest",
            str(manifest),
            "--pdf",
            str(tmp_path / "cv.pdf"),
        ]
    )

    assert code == 0
    assert captured["redlines"] == ["Forbidden Phrase"]
    assert {
        "Example Candidate",
        "example@example.com",
        "Experience",
        "Example Corp",
        "Technician",
        "Costa Rica",
        "2024",
        "2025",
        "Supported users.",
    } <= set(captured["required_texts"])
