from pathlib import Path

import pytest
from pydantic import ValidationError

from truthful_cv.manifest import ContentLine, ManifestPolicyError, load_manifest


def test_load_manifest_rejects_duplicate_line_ids(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    path.write_text(
        """schema_version: 1
language: english
lines:
  - {id: LINE-001, kind: summary, text: First, claim_ids: [CLM-001]}
  - {id: LINE-001, kind: summary, text: Second, claim_ids: [CLM-002]}
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestPolicyError, match="duplicate line ID LINE-001"):
        load_manifest(path)


def test_bullet_requires_subject_id() -> None:
    with pytest.raises(ValidationError, match="bullet requires subject_id"):
        ContentLine(
            id="LINE-001",
            kind="bullet",
            text="Supported users.",
            claim_ids=["CLM-001"],
        )


def test_skill_requires_label() -> None:
    with pytest.raises(ValidationError, match="skill requires label"):
        ContentLine(
            id="LINE-001",
            kind="skill",
            text="Windows and Microsoft 365",
            claim_ids=["CLM-001"],
        )
