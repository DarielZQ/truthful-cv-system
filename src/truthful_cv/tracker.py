import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

import yaml
from filelock import FileLock
from pydantic import BaseModel, ConfigDict, Field


class DuplicateJobError(ValueError):
    """Raised when a vacancy URL is already present in the tracker."""


class JobRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(pattern=r"^JOB-\d{3,}$")
    employer: str
    title: str
    canonical_url: str
    status: Literal[
        "discovered",
        "shortlisted",
        "prepared",
        "applied",
        "interview",
        "rejected",
        "withdrawn",
        "closed",
    ]
    collected_at: str


def load_jobs(path: Path) -> list[JobRecord]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [JobRecord.model_validate(item) for item in data.get("jobs", [])]


def add_job(path: Path, job: JobRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(f"{path}.lock")
    with lock:
        jobs = load_jobs(path)
        if any(existing.canonical_url == job.canonical_url for existing in jobs):
            raise DuplicateJobError(f"job URL already tracked: {job.canonical_url}")
        jobs.append(job)
        content = yaml.safe_dump(
            {"schema_version": 1, "jobs": [item.model_dump() for item in jobs]},
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
