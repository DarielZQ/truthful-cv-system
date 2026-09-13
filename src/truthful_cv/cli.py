import argparse
from pathlib import Path
import re
import sys

from pydantic import ValidationError
import yaml

from truthful_cv.build import build_yaml_file
from truthful_cv.manifest import ManifestPolicyError, load_manifest
from truthful_cv.profile import ProfileInputError, ProfileIntegrityError, load_profile
from truthful_cv.rendercv_adapter import build_rendercv_data
from truthful_cv.verifier import rendered_string_inventory, verify_pdf


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="truthful-cv")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-profile")
    validate.add_argument("--profile", type=Path, required=True)
    validate.add_argument("--sources", type=Path, required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--profile", type=Path, required=True)
    build.add_argument("--sources", type=Path, required=True)
    build.add_argument("--manifest", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    verify = subparsers.add_parser("verify-pdf")
    verify.add_argument("--profile", type=Path, required=True)
    verify.add_argument("--sources", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--pdf", type=Path, required=True)
    return parser


def _concise_validation_error(error: Exception) -> str:
    if isinstance(error, ValidationError):
        issue = error.errors()[0]
        safe_location = all(
            isinstance(part, int)
            or (isinstance(part, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part))
            for part in issue["loc"]
        )
        if safe_location:
            location = ".".join(str(part) for part in issue["loc"])
            return f"{location}: {issue['msg']}"
        return str(issue["msg"])
    if isinstance(error, FileNotFoundError):
        return "file not found"
    if isinstance(error, PermissionError):
        return "file access denied"
    if isinstance(error, OSError):
        return "file operation failed"
    if isinstance(error, UnicodeError):
        return "file is not valid UTF-8"
    if isinstance(error, yaml.YAMLError):
        return "invalid YAML"
    if isinstance(error, (ProfileInputError, ProfileIntegrityError, ManifestPolicyError)):
        return error.cli_message
    raise TypeError("unsupported validation error")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-profile":
            profile = load_profile(args.profile, args.sources)
            print(
                f"{profile.profile_id}: {len(profile.claims)} claims, "
                f"{len(profile.skills)} skills"
            )
            return 0
        if args.command == "build":
            output = build_yaml_file(args.profile, args.sources, args.manifest, args.output)
            print(output)
            return 0
        if args.command == "verify-pdf":
            profile = load_profile(args.profile, args.sources)
            manifest = load_manifest(args.manifest)
            document = build_rendercv_data(
                profile,
                manifest.lines,
                language=manifest.language,
                redlines=manifest.redlines,
            )
            required_texts = rendered_string_inventory(document, manifest.language)
            result = verify_pdf(
                args.pdf,
                redlines=manifest.redlines,
                required_texts=required_texts,
            )
            if result.ok:
                print("PDF verification passed")
                return 0
            for error in result.errors:
                print(error)
            return 1
    except (
        OSError,
        UnicodeError,
        ValidationError,
        yaml.YAMLError,
        ProfileInputError,
        ProfileIntegrityError,
        ManifestPolicyError,
    ) as error:
        print(f"validation error: {_concise_validation_error(error)}", file=sys.stderr)
        return 1
    return 2
