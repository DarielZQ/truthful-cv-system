from pathlib import Path

import yaml

from truthful_cv.build import build_yaml_file
from truthful_cv.manifest import ContentLine, line_signature
from truthful_cv.profile import load_profile


def test_build_yaml_file_creates_valid_rendercv_input(tmp_path: Path) -> None:
    sources = tmp_path / "sources.yaml"
    sources.write_text(
        """schema_version: 1
sources:
  - {id: SRC-001, type: cv, path: private.pdf}
""",
        encoding="utf-8",
    )
    line = ContentLine(
        id="LINE-001",
        kind="summary",
        text="Provides technical support.",
        claim_ids=["CLM-001"],
    )
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        """schema_version: 1
profile_id: example
identity:
  preferred_name: Example Candidate
  location: Costa Rica
roles: []
education: []
claims:
  - id: CLM-001
    statement: Provides technical support.
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
  - id: LINE-001
    kind: summary
    text: Provides technical support.
    claim_ids: [CLM-001]
""",
        encoding="utf-8",
    )
    output = tmp_path / "cv.yaml"

    build_yaml_file(profile, sources, manifest, output)

    document = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert document["cv"]["name"] == "Example Candidate"
    assert document["design"]["theme"] == "engineeringresumes"
    assert document["design"]["typography"]["font_size"]["body"] == "9pt"
    assert document["locale"]["language"] == "english"
