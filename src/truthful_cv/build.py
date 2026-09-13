from pathlib import Path

import yaml

from truthful_cv.manifest import load_manifest
from truthful_cv.profile import load_profile
from truthful_cv.rendercv_adapter import build_rendercv_data


def build_yaml_file(
    profile_path: Path,
    source_register_path: Path,
    manifest_path: Path,
    output_path: Path,
) -> Path:
    """Validate lineage and emit a pinned RenderCV v2.8 input file."""
    profile = load_profile(profile_path, source_register_path)
    manifest = load_manifest(manifest_path)
    document = build_rendercv_data(
        profile,
        manifest.lines,
        language=manifest.language,
        redlines=manifest.redlines,
    )
    document["design"] = {
        "theme": "engineeringresumes",
        "page": {
            "size": "us-letter",
            "top_margin": "0.45in",
            "bottom_margin": "0.45in",
            "left_margin": "0.5in",
            "right_margin": "0.5in",
            "show_footer": False,
            "show_top_note": False,
        },
        "typography": {
            "line_spacing": "0.5em",
            "font_size": {
                "body": "9pt",
                "name": "22pt",
                "headline": "9pt",
                "connections": "9pt",
                "section_titles": "1.1em",
            },
        },
        "sections": {
            "space_between_regular_entries": "0.3cm",
            "space_between_text_based_entries": "0.1cm",
        },
        "entries": {
            "highlights": {
                "space_above": "0.05cm",
                "space_between_items": "0.04cm",
            }
        },
    }
    document["locale"] = {"language": manifest.language}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(document, sort_keys=False, allow_unicode=True)
    output_path.write_text(
        "# yaml-language-server: $schema=https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/schema.json\n"
        + body,
        encoding="utf-8",
    )
    return output_path
