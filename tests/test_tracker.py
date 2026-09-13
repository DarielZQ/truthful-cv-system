from pathlib import Path
from threading import Thread

import pytest

from truthful_cv.tracker import DuplicateJobError, JobRecord, add_job, load_jobs


def test_add_job_rejects_duplicate_canonical_url(tmp_path: Path) -> None:
    tracker = tmp_path / "jobs.yaml"
    job = JobRecord(
        id="JOB-001",
        employer="Example Corp",
        title="Support Analyst",
        canonical_url="https://example.com/jobs/123",
        status="shortlisted",
        collected_at="2026-09-11",
    )

    add_job(tracker, job)

    with pytest.raises(DuplicateJobError, match="already tracked"):
        add_job(tracker, job.model_copy(update={"id": "JOB-002"}))
    assert len(load_jobs(tracker)) == 1


def test_concurrent_tracker_updates_preserve_all_jobs(tmp_path: Path) -> None:
    tracker = tmp_path / "jobs.yaml"

    def add_range(offset: int) -> None:
        for index in range(25):
            number = offset + index
            add_job(
                tracker,
                JobRecord(
                    id=f"JOB-{number:03d}",
                    employer="Example",
                    title="Support",
                    canonical_url=f"https://example.com/{number}",
                    collected_at="2026-09-11T20:00:00-06:00",
                    status="discovered",
                ),
            )

    workers = [Thread(target=add_range, args=(offset,)) for offset in (0, 100)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert len(load_jobs(tracker)) == 50
