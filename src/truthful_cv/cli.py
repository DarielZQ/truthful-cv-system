import argparse
from pathlib import Path
import re
import sys

from pydantic import ValidationError
import yaml

from truthful_cv.build import build_yaml_file
from truthful_cv.ingestion import UnsafeURLError
from truthful_cv.manifest import ManifestPolicyError, load_manifest
from truthful_cv.profile import ProfileInputError, ProfileIntegrityError, load_profile
from truthful_cv.rendercv_adapter import build_rendercv_data
from truthful_cv.verifier import rendered_string_inventory, verify_pdf
from truthful_cv.tracker import TrackerInputError
from truthful_cv.workflow import (
    WorkflowInputError,
    approve_job_requirements,
    assess_job,
    finalize_job,
    ingest_vacancy,
)


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
    vacancy = subparsers.add_parser("vacancy")
    vacancy_commands = vacancy.add_subparsers(dest="vacancy_command", required=True)
    ingest = vacancy_commands.add_parser("ingest")
    ingest.add_argument("--url", required=True)
    ingest.add_argument("--paste-file", type=Path)
    ingest.add_argument("--private-root", type=Path, default=Path("private"))
    ingest.add_argument("--title")
    ingest.add_argument("--employer")
    ingest.add_argument("--location")
    ingest.add_argument("--external-id")
    ingest.add_argument("--allow-public-host", action="append", default=[])
    approve = vacancy_commands.add_parser("approve-requirements")
    approve.add_argument("--job", required=True)
    approve.add_argument("--private-root", type=Path, default=Path("private"))
    approve.add_argument("--approve", nargs="+", required=True)
    assess = vacancy_commands.add_parser("assess")
    assess.add_argument("--job", required=True)
    assess.add_argument("--private-root", type=Path, default=Path("private"))
    assess.add_argument("--profile", type=Path, required=True)
    assess.add_argument("--sources", type=Path, required=True)
    assess.add_argument("--base-manifest", type=Path, required=True)
    finalize = vacancy_commands.add_parser("finalize")
    finalize.add_argument("--job", required=True)
    finalize.add_argument("--private-root", type=Path, default=Path("private"))
    finalize.add_argument("--profile", type=Path, required=True)
    finalize.add_argument("--sources", type=Path, required=True)
    finalize.add_argument("--manifest", type=Path)
    finalize.add_argument("--visual-approved", action="store_true")
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
    if isinstance(
        error,
        (
            ProfileInputError,
            ProfileIntegrityError,
            ManifestPolicyError,
            WorkflowInputError,
        ),
    ):
        return error.cli_message
    if isinstance(error, TrackerInputError):
        return "invalid private tracker"
    if isinstance(error, UnsafeURLError):
        return "unsafe vacancy URL"
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
        if args.command == "vacancy" and args.vacancy_command == "ingest":
            paste_text = (
                args.paste_file.read_text(encoding="utf-8") if args.paste_file is not None else None
            )
            result = ingest_vacancy(
                url=args.url,
                private_root=args.private_root,
                paste_text=paste_text,
                title=args.title,
                employer=args.employer,
                location=args.location,
                external_id=args.external_id,
                allow_public_hosts=set(args.allow_public_host),
            )
            if result.status == "paste_required":
                print(
                    f"paste_required: {result.job_id}; save the description and rerun with --paste-file"
                )
            else:
                print(f"{result.status}: {result.job_id}")
            return 0
        if args.command == "vacancy" and args.vacancy_command == "assess":
            assess_job(
                job_id=args.job,
                private_root=args.private_root,
                profile_path=args.profile,
                sources_path=args.sources,
                base_manifest_path=args.base_manifest,
            )
            print(f"assessed: {args.job}")
            return 0
        if args.command == "vacancy" and args.vacancy_command == "approve-requirements":
            approve_job_requirements(
                job_id=args.job,
                private_root=args.private_root,
                approved_ids=set(args.approve),
            )
            print(f"approved requirements: {args.job}")
            return 0
        if args.command == "vacancy" and args.vacancy_command == "finalize":
            result = finalize_job(
                job_id=args.job,
                private_root=args.private_root,
                profile_path=args.profile,
                sources_path=args.sources,
                manifest_path=args.manifest,
                visual_approved=args.visual_approved,
            )
            print(f"{result.status}: {result.job_id}")
            return 0
    except (
        OSError,
        UnicodeError,
        ValidationError,
        yaml.YAMLError,
        ProfileInputError,
        ProfileIntegrityError,
        ManifestPolicyError,
        WorkflowInputError,
        TrackerInputError,
        UnsafeURLError,
    ) as error:
        print(f"validation error: {_concise_validation_error(error)}", file=sys.stderr)
        return 1
    return 2
