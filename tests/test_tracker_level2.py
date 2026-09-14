from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from truthful_cv.tracker import (
    DuplicateJobError,
    JobRecord,
    TrackerInputError,
    load_jobs,
    reserve_job,
    update_job,
)


def test_tracker_rejects_malformed_top_level_and_jobs_containers(tmp_path: Path) -> None:
    tracker = tmp_path / "jobs.yaml"
    for malformed in ("- bad\n", "jobs: null\n", "jobs: {}\n", "jobs: scalar\n"):
        tracker.write_text(malformed, encoding="utf-8")
        with pytest.raises(TrackerInputError, match="invalid tracker"):
            load_jobs(tracker)


def test_job_id_reservation_is_lock_protected(tmp_path: Path) -> None:
    tracker = tmp_path / "jobs.yaml"

    def reserve(index: int) -> str:
        return reserve_job(
            tracker,
            employer=f"Employer {index}",
            title="Role",
            canonical_url=f"https://careers.example.com/{index}",
            provider="employer",
            external_id=f"EXT-{index}",
        ).id

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(reserve, range(20)))
    assert len(set(ids)) == 20
    assert sorted(ids)[0] == "JOB-001"
    assert sorted(ids)[-1] == "JOB-020"


def test_tracker_deduplicates_provider_external_identity(tmp_path: Path) -> None:
    tracker = tmp_path / "jobs.yaml"
    reserve_job(
        tracker,
        employer="Example",
        title="Role",
        canonical_url="https://careers.example.com/one",
        provider="greenhouse",
        external_id="42",
    )
    with pytest.raises(DuplicateJobError, match="already tracked"):
        reserve_job(
            tracker,
            employer="Example",
            title="Role",
            canonical_url="https://careers.example.com/renamed",
            provider="greenhouse",
            external_id="42",
        )


def test_tracker_update_preserves_resume_artifacts_and_state(tmp_path: Path) -> None:
    tracker = tmp_path / "jobs.yaml"
    job = reserve_job(
        tracker,
        employer="Example",
        title="Role",
        canonical_url="https://careers.example.com/one",
        provider="employer",
        status="captured",
        content_hash="sha256:" + "1" * 64,
    )
    update_job(
        tracker,
        job.id,
        status="requirements_review",
        snapshot_ref="vacancies/JOB-001/snapshot.yaml",
        requirements_ref="vacancies/JOB-001/requirements.yaml",
    )
    update_job(
        tracker,
        job.id,
        status="approved",
        approved_requirements_sha256="a" * 64,
    )
    updated = update_job(
        tracker,
        job.id,
        status="assessed",
        assessment_ref="vacancies/JOB-001/fit-report.yaml",
        manifest_ref="vacancies/JOB-001/tailored-manifest.yaml",
        tailored_manifest_sha256="b" * 64,
    )
    assert updated.status == "assessed"
    reloaded = load_jobs(tracker)[0]
    assert reloaded.snapshot_ref.endswith("snapshot.yaml")
    assert reloaded.assessment_ref.endswith("fit-report.yaml")


def test_job_record_rejects_attacker_controlled_identifier() -> None:
    with pytest.raises(ValueError):
        JobRecord(
            id="../../secret",
            employer="Example",
            title="Role",
            canonical_url="https://example.com/1",
            status="discovered",
            collected_at="2026-09-13T00:00:00Z",
        )


def test_tracker_prevents_workflow_state_regression(tmp_path: Path) -> None:
    tracker = tmp_path / "jobs.yaml"
    job = reserve_job(
        tracker, employer="Example", title="Role",
        canonical_url="https://example.com/1", status="captured",
        content_hash="sha256:" + "2" * 64,
    )
    update_job(
        tracker,
        job.id,
        status="requirements_review",
        snapshot_ref="vacancies/JOB-001/snapshot.yaml",
        requirements_ref="vacancies/JOB-001/requirements.yaml",
    )
    update_job(
        tracker,
        job.id,
        status="approved",
        approved_requirements_sha256="c" * 64,
    )
    with pytest.raises(TrackerInputError, match="transition"):
        update_job(tracker, job.id, status="requirements_review")


def test_tracker_rejects_skipped_and_cross_phase_workflow_transitions(tmp_path: Path) -> None:
    tracker = tmp_path / "jobs.yaml"
    job = reserve_job(
        tracker,
        employer="Example",
        title="Role",
        canonical_url="https://example.com/2",
        status="captured",
        content_hash="sha256:" + "3" * 64,
    )
    update_job(
        tracker,
        job.id,
        status="requirements_review",
        snapshot_ref="vacancies/JOB-001/snapshot.yaml",
        requirements_ref="vacancies/JOB-001/requirements.yaml",
    )
    with pytest.raises(TrackerInputError, match="transition"):
        update_job(tracker, job.id, status="finalized")
    with pytest.raises(TrackerInputError, match="transition"):
        update_job(tracker, job.id, status="captured")


def test_tracker_rejects_noninitial_reserved_state(tmp_path: Path) -> None:
    with pytest.raises(TrackerInputError, match="initial"):
        reserve_job(
            tmp_path / "tracker.yaml",
            employer="Example",
            title="Role",
            canonical_url="https://example.com/3",
            status="finalized",
        )


def test_tracker_rejects_same_state_integrity_hash_mutation(tmp_path: Path) -> None:
    tracker = tmp_path / "tracker.yaml"
    job = reserve_job(
        tracker,
        employer="Example",
        title="Role",
        canonical_url="https://example.com/4",
        status="captured",
        content_hash="sha256:" + "4" * 64,
    )
    with pytest.raises(TrackerInputError, match="fields"):
        update_job(tracker, job.id, artifact_sha256="0" * 64)


def test_tracker_requires_integrity_fields_on_lifecycle_transition(tmp_path: Path) -> None:
    tracker = tmp_path / "tracker.yaml"
    job = reserve_job(
        tracker,
        employer="Example",
        title="Role",
        canonical_url="https://example.com/5",
        status="captured",
        content_hash="sha256:" + "1" * 64,
    )
    with pytest.raises(TrackerInputError, match="required fields"):
        update_job(tracker, job.id, status="requirements_review")


def test_job_record_rejects_incomplete_approved_lifecycle_state() -> None:
    with pytest.raises(ValueError, match="approved_requirements_sha256"):
        JobRecord(
            id="JOB-999",
            employer="Example",
            title="Role",
            canonical_url="https://example.com/999",
            status="approved",
            collected_at="2026-09-13T00:00:00Z",
        )
