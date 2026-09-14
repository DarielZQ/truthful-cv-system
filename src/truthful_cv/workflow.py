import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml
from filelock import FileLock
from pydantic import BaseModel

from truthful_cv.build import build_yaml_file
from truthful_cv.ingestion import SafeFetcher, validate_url_syntax
from truthful_cv.matcher import JobRequirement, assess_fit
from truthful_cv.manifest import load_manifest, validate_manifest
from truthful_cv.profile import load_profile
from truthful_cv.providers import classify_provider
from truthful_cv.rendercv_adapter import build_rendercv_data
from truthful_cv.storage import safe_private_path
from truthful_cv.tailor import rank_lines_for_job
from truthful_cv.requirements import (
    approve_requirements,
    extract_requirement_drafts,
    load_approved_requirements,
    load_requirements,
    save_requirement_drafts,
)
from truthful_cv.tracker import (
    DuplicateJobError,
    JobRecord,
    load_jobs,
    reserve_job,
    update_job,
)
from truthful_cv.vacancy import (
    AcquisitionMode,
    VacancySnapshot,
    extract_posting,
    load_snapshot,
    save_snapshot,
)
from truthful_cv.verifier import VerificationResult, rendered_string_inventory, verify_pdf


class WorkflowResult(BaseModel):
    status: str
    job_id: str
    deliverable: Path | None = None


class WorkflowInputError(ValueError):
    """Expected private workflow input failure with a fixed CLI message."""

    cli_message = "vacancy workflow input is invalid"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical_url(url: str) -> str:
    parsed = urlsplit(url)
    tracking = {"fbclid", "gclid", "msclkid", "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term"}
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() not in tracking
    ]
    return urlunsplit(
        (
            parsed.scheme.lower(),
            (parsed.hostname or "").lower().rstrip("."),
            parsed.path.rstrip("/") or "/",
            urlencode(query),
            "",
        )
    )


def _existing(path: Path, canonical: str) -> JobRecord | None:
    return next((item for item in load_jobs(path) if item.canonical_url == canonical), None)


def _reserve_or_resume(
    tracker: Path,
    *,
    canonical: str,
    provider: str,
    external_id: str | None,
    employer: str,
    title: str,
    status: str,
    content_hash: str | None = None,
) -> JobRecord:
    current = _existing(tracker, canonical)
    if current and current.status != "pending_capture":
        return current
    if current and current.status == status:
        return current
    if current:
        return update_job(
            tracker,
            current.id,
            provider=provider,
            external_id=external_id or current.external_id,
            employer=employer,
            title=title,
            status=status,
            content_hash=content_hash or current.content_hash,
        )
    try:
        return reserve_job(
            tracker,
            employer=employer,
            title=title,
            canonical_url=canonical,
            provider=provider,
            external_id=external_id,
            content_hash=content_hash,
            status=status,
        )
    except DuplicateJobError:
        matches = [
            item
            for item in load_jobs(tracker)
            if item.canonical_url == canonical
            or (content_hash and item.content_hash == content_hash)
            or (provider and external_id and item.provider == provider and item.external_id == external_id)
        ]
        if not matches:
            raise
        return matches[0]


def _persist_capture(
    *, private_root: Path, tracker: Path, job: JobRecord,
    snapshot: VacancySnapshot, description: str,
) -> JobRecord:
    with FileLock(f"{tracker}.capture.lock"):
        current = next(item for item in load_jobs(tracker) if item.id == job.id)
        if current.status not in {"pending_capture", "captured"}:
            return current
        snapshot_path = save_snapshot(private_root, snapshot)
        requirements_path = safe_private_path(
            private_root.resolve(), "vacancies", job.id, "requirements.yaml"
        )
        save_requirement_drafts(requirements_path, extract_requirement_drafts(description))
        return update_job(
            tracker,
            job.id,
            status="requirements_review",
            snapshot_ref=str(snapshot_path.relative_to(private_root.resolve()).as_posix()),
            requirements_ref=str(requirements_path.relative_to(private_root.resolve()).as_posix()),
        )


def ingest_vacancy(
    *,
    url: str,
    private_root: Path,
    paste_text: str | None = None,
    title: str | None = None,
    employer: str | None = None,
    location: str | None = None,
    external_id: str | None = None,
    fetcher: SafeFetcher | None = None,
    allow_public_hosts: set[str] | None = None,
) -> WorkflowResult:
    validate_url_syntax(url)
    provider = classify_provider(url)
    canonical = _canonical_url(url)
    root = private_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    tracker = safe_private_path(root, "tracker.yaml")
    posting = None
    mode = AcquisitionMode.USER_PASTE
    reason = "user_paste"
    description = "\n".join(" ".join(line.split()) for line in (paste_text or "").splitlines() if line.strip())
    if not description:
        outcome = (fetcher or SafeFetcher(allow_public_hosts=allow_public_hosts)).fetch(url)
        if outcome.paste_required:
            job = _reserve_or_resume(
                tracker,
                canonical=canonical,
                provider=provider.value,
                external_id=external_id,
                employer=employer or "Pending capture",
                title=title or "Pending capture",
                status="pending_capture",
            )
            return WorkflowResult(status="paste_required", job_id=job.id)
        try:
            posting = extract_posting(outcome.body or b"", outcome.content_type or "text/html")
        except (UnicodeError, ValueError):
            job = _reserve_or_resume(
                tracker,
                canonical=canonical,
                provider=provider.value,
                external_id=external_id,
                employer=employer or "Pending capture",
                title=title or "Pending capture",
                status="pending_capture",
            )
            return WorkflowResult(status="paste_required", job_id=job.id)
        canonical = _canonical_url(outcome.final_url or url)
        provider = classify_provider(outcome.final_url or url)
        mode = AcquisitionMode.PUBLIC_URL
        reason = "public_get"
        description = posting.description
        title = posting.title
        employer = posting.employer
        location = posting.location
        external_id = posting.external_id or external_id
    if not title or not employer or len(description) < 10:
        raise WorkflowInputError("paste metadata and meaningful description are required")
    digest = "sha256:" + sha256(description.encode("utf-8")).hexdigest()
    existing = _existing(tracker, canonical)
    if existing and existing.status != "pending_capture":
        return WorkflowResult(status=existing.status, job_id=existing.id)
    mirrored = next((item for item in load_jobs(tracker) if item.content_hash == digest), None)
    if mirrored is not None:
        return WorkflowResult(status=mirrored.status, job_id=mirrored.id)
    job = _reserve_or_resume(
        tracker,
        canonical=canonical,
        provider=provider.value,
        external_id=external_id,
        employer=employer,
        title=title,
        status="captured",
        content_hash=digest,
    )
    if job.canonical_url != canonical or job.content_hash != digest:
        return WorkflowResult(status=job.status, job_id=job.id)
    snapshot = VacancySnapshot(
        job_id=job.id,
        source_url=url,
        canonical_url=canonical,
        provider=provider,
        external_id=external_id,
        acquisition_mode=mode,
        retrieved_at=_now(),
        title=title,
        employer=employer,
        location=location,
        posted_at=posting.posted_at if posting else None,
        active=posting.active if posting else None,
        description=description,
        content_hash=digest,
        policy_reason=reason,
    )
    stored = _persist_capture(
        private_root=private_root,
        tracker=tracker,
        job=job,
        snapshot=snapshot,
        description=description,
    )
    return WorkflowResult(status=stored.status, job_id=job.id)


def _atomic_yaml(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as temp:
            yaml.safe_dump(data, temp, sort_keys=False, allow_unicode=True)
            temp.flush()
            os.fsync(temp.fileno())
            temporary_name = temp.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name and Path(temporary_name).exists():
            Path(temporary_name).unlink()


def assess_job(
    *,
    job_id: str,
    private_root: Path,
    profile_path: Path,
    sources_path: Path,
    base_manifest_path: Path,
) -> Path:
    if not re.fullmatch(r"JOB-\d{3,}", job_id):
        raise WorkflowInputError("invalid job identifier")
    root = private_root.resolve()
    tracker = safe_private_path(root, "tracker.yaml")
    job = next((item for item in load_jobs(tracker) if item.id == job_id), None)
    if job is None or job.status != "approved":
        raise WorkflowInputError("approved job is required")
    requirements_path = safe_private_path(root, "vacancies", job_id, "requirements.yaml")
    expected_requirements_ref = str(requirements_path.relative_to(root).as_posix())
    expected_snapshot_ref = f"vacancies/{job_id}/snapshot.yaml"
    if (
        job.requirements_ref != expected_requirements_ref
        or job.snapshot_ref != expected_snapshot_ref
        or not job.approved_requirements_sha256
    ):
        raise WorkflowInputError("approved vacancy binding is invalid")
    if _file_sha256(requirements_path) != job.approved_requirements_sha256:
        raise WorkflowInputError("approved requirements changed")
    try:
        snapshot = load_snapshot(root, job_id)
    except (OSError, ValueError) as error:
        raise WorkflowInputError("approved vacancy binding is invalid") from error
    computed_snapshot_hash = "sha256:" + sha256(snapshot.description.encode("utf-8")).hexdigest()
    if snapshot.content_hash != job.content_hash or snapshot.content_hash != computed_snapshot_hash:
        raise WorkflowInputError("approved vacancy binding is invalid")
    try:
        drafts = load_approved_requirements(requirements_path)
    except ValueError as error:
        raise WorkflowInputError("approved requirements are required") from error
    requirements = [JobRequirement.model_validate(item.model_dump()) for item in drafts]
    profile = load_profile(profile_path, sources_path)
    try:
        base_path = base_manifest_path.resolve()
        relative_base = base_path.relative_to(root)
        safe_private_path(root, relative_base)
        base_manifest = load_manifest(base_path)
        validate_manifest(
            base_manifest.lines,
            profile,
            require_line_approval=True,
            language=base_manifest.language,
        )
    except (ValueError, OSError) as error:
        raise WorkflowInputError("reviewed signed base manifest is required") from error
    assessment = assess_fit(profile, requirements)
    if assessment.hard_filter_failures:
        raise WorkflowInputError("unresolved hard filters block assessment")
    ranked_manifest = rank_lines_for_job(profile, base_manifest.lines, requirements)
    selected = [
        item.line
        for item in ranked_manifest
        if item.line.kind in {"headline", "summary"} or item.score > 0
    ]
    tailored = safe_private_path(root, "vacancies", job_id, "tailored-manifest.yaml")
    _atomic_yaml(
        tailored,
        {
            "schema_version": base_manifest.schema_version,
            "language": base_manifest.language,
            "summary_voice": base_manifest.summary_voice,
            "lines": [line.model_dump(mode="json") for line in selected],
            "redlines": base_manifest.redlines,
        },
    )
    scores: dict[str, float] = {}
    for match in assessment.matches:
        for claim_id in match.claim_ids:
            scores[claim_id] = scores.get(claim_id, 0.0) + match.retrieval_score
    ranked = [
        {"claim_id": claim_id, "retrieval_score": score}
        for claim_id, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    ]
    claims = {claim.id: claim for claim in profile.claims}
    ranked_lines = [
        {"claim_id": item["claim_id"], "text": claims[item["claim_id"]].statement,
         "retrieval_score": item["retrieval_score"]}
        for item in ranked
    ]
    report = safe_private_path(root, "vacancies", job_id, "fit-report.yaml")
    _atomic_yaml(
        report,
        {
            "schema_version": 1,
            "job_id": job_id,
            "assessment": assessment.model_dump(mode="json"),
            "ranked_approved_claims": ranked,
            "ranked_approved_lines": ranked_lines,
            "notice": "Tag overlap is retrieval only; STRONG/DEEP requires a reasoned human override.",
        },
    )
    update_job(
        tracker,
        job_id,
        status="assessed",
        assessment_ref=str(report.relative_to(root).as_posix()),
        manifest_ref=str(tailored.relative_to(root).as_posix()),
        tailored_manifest_sha256=_file_sha256(tailored),
    )
    return report


def approve_job_requirements(*, job_id: str, private_root: Path, approved_ids: set[str]) -> None:
    if not re.fullmatch(r"JOB-\d{3,}", job_id):
        raise WorkflowInputError("invalid job identifier")
    root = private_root.resolve()
    tracker = safe_private_path(root, "tracker.yaml")
    job = next((item for item in load_jobs(tracker) if item.id == job_id), None)
    if job is None or job.status != "requirements_review":
        raise WorkflowInputError("requirements review state is required")
    path = safe_private_path(root, "vacancies", job_id, "requirements.yaml")
    try:
        drafts = load_requirements(path)
        approve_requirements(path, drafts, approved_ids)
    except ValueError as error:
        raise WorkflowInputError("requirement approval is invalid") from error
    update_job(
        tracker,
        job_id,
        status="approved",
        approved_requirements_sha256=_file_sha256(path),
    )


def _safe_component(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value)
    value = re.sub(r"[\s_]+", "_", value).strip(" ._")
    return value[:80] or "Unknown"


def _default_runner(command: list[str], _expected_pdf: Path) -> None:
    subprocess.run(
        command,
        check=True,
        shell=False,
        timeout=180,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _copy_verified(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        shutil.copyfile(source, temporary)
        with temporary.open("rb+") as stream:
            os.fsync(stream.fileno())
        if sha256(source.read_bytes()).digest() != sha256(temporary.read_bytes()).digest():
            raise OSError("deliverable copy verification failed")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def finalize_job(
    *,
    job_id: str,
    private_root: Path,
    profile_path: Path,
    sources_path: Path,
    manifest_path: Path | None,
    visual_approved: bool,
    runner: Callable[[list[str], Path], None] = _default_runner,
    verifier: Callable[..., VerificationResult] = verify_pdf,
) -> WorkflowResult:
    if not re.fullmatch(r"JOB-\d{3,}", job_id):
        raise WorkflowInputError("invalid job identifier")
    root = private_root.resolve()
    tracker = safe_private_path(root, "tracker.yaml")
    job = next((item for item in load_jobs(tracker) if item.id == job_id), None)
    if job is None:
        raise WorkflowInputError("job not found")
    if not job.manifest_ref:
        raise WorkflowInputError("tracked tailored manifest is required")
    try:
        tracked_manifest = safe_private_path(root, job.manifest_ref)
    except ValueError as error:
        raise WorkflowInputError("tracked tailored manifest is invalid") from error
    if manifest_path is not None and manifest_path.resolve() != tracked_manifest:
        raise WorkflowInputError("tracked tailored manifest mismatch")
    if not job.tailored_manifest_sha256 or _file_sha256(tracked_manifest) != job.tailored_manifest_sha256:
        raise WorkflowInputError("tracked tailored manifest changed")
    input_path = safe_private_path(root, "generated", job_id, "input.yaml")
    pdf_path = safe_private_path(root, "generated", job_id, "cv.pdf")
    profile = load_profile(profile_path, sources_path)
    manifest = load_manifest(tracked_manifest)
    document = build_rendercv_data(
        profile, manifest.lines, language=manifest.language, redlines=manifest.redlines
    )
    required_texts = rendered_string_inventory(document, manifest.language)

    if visual_approved:
        if job.status != "rendered" or not job.artifact_sha256:
            raise WorkflowInputError("prior rendered state is required")
        if not pdf_path.is_file():
            raise WorkflowInputError("rendered artifact is missing")
        current_hash = sha256(pdf_path.read_bytes()).hexdigest()
        if current_hash != job.artifact_sha256:
            raise WorkflowInputError("rendered artifact changed")
        if not job.render_input_sha256 or _file_sha256(input_path) != job.render_input_sha256:
            raise WorkflowInputError("render input changed")
        verification = verifier(pdf_path, redlines=manifest.redlines, required_texts=required_texts)
        if not verification.ok:
            raise WorkflowInputError("strict PDF verification failed")
        candidate = profile.identity.preferred_name if profile.identity else "Candidate"
        destination = safe_private_path(
            root,
            "deliverables",
            f"{_safe_component(candidate)}_CV_{_safe_component(job.employer)}_"
            f"{_safe_component(job.title)}_{job_id}.pdf",
        )
        _copy_verified(pdf_path, destination)
        if sha256(destination.read_bytes()).hexdigest() != job.artifact_sha256:
            raise WorkflowInputError("deliverable hash verification failed")
        update_job(
            tracker,
            job_id,
            status="finalized",
            deliverable_ref=str(destination.relative_to(root).as_posix()),
        )
        return WorkflowResult(status="finalized", job_id=job_id, deliverable=destination)

    if job.status != "assessed":
        raise WorkflowInputError("assessed job is required")
    build_yaml_file(profile_path, sources_path, tracked_manifest, input_path)
    input_path = input_path.resolve()
    pdf_path = pdf_path.resolve()
    command = [
        sys.executable,
        "-m",
        "rendercv",
        "render",
        str(input_path),
        "--pdf-path",
        str(pdf_path),
        "--dont-generate-markdown",
        "--dont-generate-html",
        "--dont-generate-png",
        "--quiet",
    ]
    try:
        runner(command, pdf_path)
    except (subprocess.SubprocessError, TimeoutError, OSError) as error:
        raise WorkflowInputError("renderer failed") from error
    if not pdf_path.is_file():
        raise WorkflowInputError("renderer failed")
    verification = verifier(pdf_path, redlines=manifest.redlines, required_texts=required_texts)
    if not verification.ok:
        raise WorkflowInputError("strict PDF verification failed")
    artifact_hash = sha256(pdf_path.read_bytes()).hexdigest()
    update_job(
        tracker,
        job_id,
        status="rendered",
        generated_ref=str(pdf_path.relative_to(root).as_posix()),
        render_input_sha256=_file_sha256(input_path),
        artifact_sha256=artifact_hash,
    )
    return WorkflowResult(status="visual_approval_required", job_id=job_id)
