from pathlib import Path
import re

from truthful_cv.models import ClaimCategory


ROOT = Path(__file__).resolve().parents[1]


def test_profile_schema_lists_implemented_claim_categories() -> None:
    text = (ROOT / "docs" / "profile-schema.md").read_text(encoding="utf-8")
    match = re.search(r"^- Claim category: (.+)\.$", text, flags=re.MULTILINE)

    assert match is not None
    documented = {value.strip(" `") for value in match.group(1).split(",")}
    assert documented == {category.value for category in ClaimCategory}


def test_handoff_does_not_instruct_root_history_rewrite() -> None:
    text = (ROOT / "HANDOFF.md").read_text(encoding="utf-8").casefold()

    assert "rewrite the local root commit" not in text
    assert "rewrite history" not in text
