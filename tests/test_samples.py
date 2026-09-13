from pathlib import Path

import yaml

from truthful_cv.manifest import load_manifest
from truthful_cv.profile import load_profile
from truthful_cv.rendercv_adapter import build_rendercv_data


SAMPLES = Path(__file__).parents[1] / "samples"


def test_sanitized_examples_validate_and_build() -> None:
    profile = load_profile(
        SAMPLES / "profile.example.yaml",
        SAMPLES / "source-register.example.yaml",
    )
    manifest = load_manifest(SAMPLES / "manifest.example.yaml")

    document = build_rendercv_data(
        profile,
        manifest.lines,
        language=manifest.language,
        redlines=manifest.redlines,
    )

    assert document["cv"]["name"] == "Example Candidate"
    assert list(document["cv"]["sections"]) == ["experience", "education"]


def test_job_requirement_sample_has_all_four_fit_scenarios() -> None:
    data = yaml.safe_load((SAMPLES / "job-requirements.example.yaml").read_text("utf-8"))

    assert {item["expected_fit"] for item in data["scenarios"]} == {
        "deep",
        "strong",
        "partial",
        "absent",
    }
