import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

import yaml
from filelock import FileLock
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class DuplicateJobError(ValueError):
    """Raised when a vacancy identity is already present in the tracker."""


class TrackerInputError(ValueError):
    """Raised for malformed tracker input without exposing its contents."""


JobStatus = Literal[
    "discovered",
    "pending_capture",
    "captured",
    "requirements_review",
    "approved",
    "assessed",
    "shortlisted",
    "prepared",
    "rendered",
    "finalized",
    "applied",
    "interview",
    "rejected",
    "withdrawn",
    "closed",
]


class JobRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(pattern=r"^JOB-\d{3,}$")
    employer: str
    title: str
    canonical_url: str
    provider: str | None = None
    external_id: str | None = None
    status: JobStatus
    collected_at: str
    updated_at: str | None = None
    snapshot_ref: str | None = None
    requirements_ref: str | None = None
    assessment_ref: str | None = None
    manifest_ref: str | None = None
    generated_ref: str | None = None
    deliverable_ref: str | None = None
    content_hash: str | None = None
    approved_requirements_sha256: str | None = None
    tailored_manifest_sha256: str | None = None
    render_input_sha256: str | None = None
    artifact_sha256: str | None = None

    @model_validator(mode="after")
    def require_lifecycle_integrity(self) -> "JobRecord":
        required_by_status = {
            "captured": {"content_hash"},
            "requirements_review": {"content_hash", "snapshot_ref", "requirements_ref"},
            "approved": {
                "content_hash", "snapshot_ref", "requirements_ref",
                "approved_requirements_sha256",
            },
            "assessed": {
                "content_hash", "snapshot_ref", "requirements_ref",
                "approved_requirements_sha256", "assessment_ref", "manifest_ref",
                "tailored_manifest_sha256",
            },
            "rendered": {
                "content_hash", "snapshot_ref", "requirements_ref",
                "approved_requirements_sha256", "assessment_ref", "manifest_ref",
                "tailored_manifest_sha256", "generated_ref", "render_input_sha256",
                "artifact_sha256",
            },
            "finalized": {
                "content_hash", "snapshot_ref", "requirements_ref",
                "approved_requirements_sha256", "assessment_ref", "manifest_ref",
                "tailored_manifest_sha256", "generated_ref", "render_input_sha256",
                "artifact_sha256", "deliverable_ref",
            },
        }
        missing = sorted(
            field
            for field in required_by_status.get(self.status, set())
            if not getattr(self, field)
        )
        if missing:
            raise ValueError(f"{missing[0]} is required for {self.status} state")
        return self


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_jobs(path: Path) -> list[JobRecord]:
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            raise TrackerInputError("invalid tracker structure")
        return [JobRecord.model_validate(item) for item in data["jobs"]]
    except TrackerInputError:
        raise
    except (OSError, UnicodeError, yaml.YAMLError, ValidationError, TypeError) as error:
        raise TrackerInputError("invalid tracker data") from error


def _write(path: Path, jobs: list[JobRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(
        {"schema_version": 1, "jobs": [item.model_dump(mode="json") for item in jobs]},
        sort_keys=False,
        allow_unicode=True,
    )
    temporary_name: str | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name and Path(temporary_name).exists():
            Path(temporary_name).unlink()


def _duplicate(jobs: list[JobRecord], candidate: JobRecord) -> JobRecord | None:
    for existing in jobs:
        if candidate.content_hash and existing.content_hash == candidate.content_hash:
            return existing
        if existing.canonical_url == candidate.canonical_url:
            return existing
        if (
            candidate.provider
            and candidate.external_id
            and existing.provider == candidate.provider
            and existing.external_id == candidate.external_id
        ):
            return existing
    return None


def add_job(path: Path, job: JobRecord) -> None:
    if job.status not in {"discovered", "shortlisted"}:
        raise TrackerInputError("invalid initial tracker state")
    path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(f"{path}.lock"):
        jobs = load_jobs(path)
        if _duplicate(jobs, job):
            raise DuplicateJobError("job identity already tracked")
        jobs.append(job)
        _write(path, jobs)


def reserve_job(
    path: Path,
    *,
    employer: str,
    title: str,
    canonical_url: str,
    provider: str | None = None,
    external_id: str | None = None,
    content_hash: str | None = None,
    status: JobStatus = "discovered",
) -> JobRecord:
    if status not in {"discovered", "pending_capture", "captured"}:
        raise TrackerInputError("invalid initial tracker state")
    if status == "captured" and not content_hash:
        raise TrackerInputError("captured initial state requires content hash")
    path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(f"{path}.lock"):
        jobs = load_jobs(path)
        numbers = [int(item.id.removeprefix("JOB-")) for item in jobs]
        candidate = JobRecord(
            id=f"JOB-{max(numbers, default=0) + 1:03d}",
            employer=employer,
            title=title,
            canonical_url=canonical_url,
            provider=provider,
            external_id=external_id,
            content_hash=content_hash,
            status=status,
            collected_at=_now(),
        )
        existing = _duplicate(jobs, candidate)
        if existing:
            raise DuplicateJobError("job identity already tracked")
        jobs.append(candidate)
        _write(path, jobs)
        return candidate


def update_job(path: Path, job_id: str, **changes: object) -> JobRecord:
    if not __import__("re").fullmatch(r"JOB-\d{3,}", job_id):
        raise TrackerInputError("invalid job identifier")
    path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(f"{path}.lock"):
        jobs = load_jobs(path)
        indexes = [index for index, item in enumerate(jobs) if item.id == job_id]
        if not indexes:
            raise TrackerInputError("job not found")
        index = indexes[0]
        old_status = jobs[index].status
        new_status = changes.get("status", old_status)
        allowed_transitions = {
            "discovered": {"pending_capture", "captured", "closed"},
            "pending_capture": {"captured", "closed"},
            "captured": {"requirements_review", "closed"},
            "requirements_review": {"approved", "closed"},
            "approved": {"assessed", "closed"},
            "assessed": {"rendered", "closed"},
            "rendered": {"finalized", "closed"},
            "finalized": {"applied", "withdrawn", "closed"},
            "shortlisted": {"prepared", "closed"},
            "prepared": {"applied", "withdrawn", "closed"},
            "applied": {"interview", "rejected", "withdrawn", "closed"},
            "interview": {"rejected", "withdrawn", "closed"},
            "rejected": {"closed"},
            "withdrawn": {"closed"},
            "closed": set(),
        }
        if (
            isinstance(new_status, str)
            and new_status != old_status
            and new_status not in allowed_transitions.get(old_status, set())
        ):
            raise TrackerInputError("invalid workflow transition")
        allowed_fields = {
            ("discovered", "pending_capture"): {
                "status", "provider", "external_id", "employer", "title"
            },
            ("discovered", "captured"): {
                "status", "provider", "external_id", "employer", "title", "content_hash"
            },
            ("pending_capture", "captured"): {
                "status", "provider", "external_id", "employer", "title", "content_hash"
            },
            ("captured", "requirements_review"): {
                "status", "snapshot_ref", "requirements_ref"
            },
            ("requirements_review", "approved"): {
                "status", "approved_requirements_sha256"
            },
            ("approved", "assessed"): {
                "status", "assessment_ref", "manifest_ref", "tailored_manifest_sha256"
            },
            ("assessed", "rendered"): {
                "status", "generated_ref", "render_input_sha256", "artifact_sha256"
            },
            ("rendered", "finalized"): {"status", "deliverable_ref"},
        }
        requested_fields = set(changes)
        if new_status == old_status:
            permitted_fields: set[str] = set()
        else:
            permitted_fields = allowed_fields.get((old_status, new_status), {"status"})
        if not requested_fields <= permitted_fields:
            raise TrackerInputError("invalid fields for workflow transition")
        required_fields = {
            ("captured", "requirements_review"): {"snapshot_ref", "requirements_ref"},
            ("requirements_review", "approved"): {"approved_requirements_sha256"},
            ("approved", "assessed"): {
                "assessment_ref", "manifest_ref", "tailored_manifest_sha256"
            },
            ("assessed", "rendered"): {
                "generated_ref", "render_input_sha256", "artifact_sha256"
            },
            ("rendered", "finalized"): {"deliverable_ref"},
        }.get((old_status, new_status), set())
        if any(not changes.get(field) for field in required_fields):
            raise TrackerInputError("required fields missing for workflow transition")
        payload = {**changes, "updated_at": _now()}
        try:
            updated = jobs[index].model_copy(update=payload)
            updated = JobRecord.model_validate(updated.model_dump())
        except ValidationError as error:
            raise TrackerInputError("invalid tracker update") from error
        duplicate = _duplicate([item for offset, item in enumerate(jobs) if offset != index], updated)
        if duplicate:
            raise DuplicateJobError("job identity already tracked")
        jobs[index] = updated
        _write(path, jobs)
        return updated
