from hashlib import sha256
from pathlib import Path

import pytest
import yaml

from truthful_cv.manifest import ContentLine, line_signature
from truthful_cv.profile import load_profile
from truthful_cv.requirements import load_requirements
from truthful_cv.tracker import load_jobs
from truthful_cv.verifier import VerificationResult
from truthful_cv.workflow import (
    WorkflowInputError,
    approve_job_requirements,
    assess_job,
    finalize_job,
    ingest_vacancy,
)


def _prepared_inputs(tmp_path: Path, description: str = "Requirements:\nWindows support"):
    root = tmp_path / "private"
    root.mkdir()
    sources = root / "sources.yaml"
    sources.write_text("schema_version: 1\nsources: [{id: SRC-001}]\n", encoding="utf-8")
    profile = root / "profile.yaml"
    profile.write_text("""schema_version: 1
profile_id: example
identity: {preferred_name: Example Candidate}
roles: []
education: []
claims:
  - id: CLM-001
    statement: I support Windows users.
    category: knowledge
    tier: C
    attribution: individual
    status: approved
    source_ids: [SRC-001]
    tags: [windows, support]
skills: []
""", encoding="utf-8")
    lines = [
        ContentLine(id="LINE-001", kind="summary", text="I support Windows users.", claim_ids=["CLM-001"]),
        ContentLine(id="LINE-002", kind="summary", text="I provide documented Windows support for users who need clear and practical technical assistance.", claim_ids=["CLM-001"]),
        ContentLine(id="LINE-003", kind="summary", text="I use approved support knowledge to help Windows users resolve technical requests with consistent guidance.", claim_ids=["CLM-001"]),
    ]
    loaded_profile = load_profile(profile, sources)
    signatures = [line_signature(line, loaded_profile, "english") for line in lines]
    profile.write_text(
        profile.read_text(encoding="utf-8")
        + yaml.safe_dump({"approved_line_signatures": signatures}, sort_keys=False),
        encoding="utf-8",
    )
    base = root / "base.yaml"
    base.write_text(yaml.safe_dump({"schema_version": 1, "language": "english",
                                    "lines": [line.model_dump(mode="json") for line in lines]},
                                   sort_keys=False), encoding="utf-8")
    job = ingest_vacancy(url="https://jobs.lever.co/acme/abc", private_root=root,
        paste_text=description, title="Support", employer="Acme")
    ids = {item.id for item in load_requirements(root / "vacancies" / job.job_id / "requirements.yaml")}
    approve_job_requirements(job_id=job.job_id, private_root=root, approved_ids=ids)
    return root, profile, sources, base, job.job_id


def test_assess_creates_and_binds_exact_approved_tailored_manifest(tmp_path: Path) -> None:
    root, profile, sources, base, job_id = _prepared_inputs(tmp_path)
    report = assess_job(job_id=job_id, private_root=root, profile_path=profile,
                        sources_path=sources, base_manifest_path=base)
    tracked = load_jobs(root / "tracker.yaml")[0]
    assert report.exists() and tracked.status == "assessed"
    assert tracked.manifest_ref == f"vacancies/{job_id}/tailored-manifest.yaml"
    tailored = root / tracked.manifest_ref
    assert tailored.read_text(encoding="utf-8").count("I support Windows users.") == 1
    assert str(root) not in tracked.manifest_ref


def test_visual_approval_is_two_stage_and_bound_to_exact_bytes(tmp_path: Path) -> None:
    root, profile, sources, base, job_id = _prepared_inputs(tmp_path)
    assess_job(job_id=job_id, private_root=root, profile_path=profile,
               sources_path=sources, base_manifest_path=base)
    calls = []
    def runner(command: list[str], output: Path) -> None:
        calls.append(command)
        assert Path(command[4]).is_absolute()
        assert Path(command[6]).is_absolute()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"%PDF-1.7\nexact")
    def verifier(_path: Path, **_kwargs) -> VerificationResult:
        return VerificationResult(ok=True, redline_hits=[], errors=[])
    with pytest.raises(WorkflowInputError, match="prior rendered state"):
        finalize_job(job_id=job_id, private_root=root, profile_path=profile,
                     sources_path=sources, manifest_path=None, visual_approved=True,
                     runner=runner, verifier=verifier)
    first = finalize_job(job_id=job_id, private_root=root, profile_path=profile,
                         sources_path=sources, manifest_path=None, visual_approved=False,
                         runner=runner, verifier=verifier)
    assert first.status == "visual_approval_required"
    tracked = load_jobs(root / "tracker.yaml")[0]
    assert tracked.status == "rendered"
    assert tracked.artifact_sha256 == sha256(b"%PDF-1.7\nexact").hexdigest()
    second = finalize_job(job_id=job_id, private_root=root, profile_path=profile,
                          sources_path=sources, manifest_path=None, visual_approved=True,
                          runner=lambda *_: pytest.fail("must not rerender"), verifier=verifier)
    assert second.status == "finalized" and len(calls) == 1


def test_visual_approval_rejects_changed_artifact(tmp_path: Path) -> None:
    root, profile, sources, base, job_id = _prepared_inputs(tmp_path)
    assess_job(job_id=job_id, private_root=root, profile_path=profile,
               sources_path=sources, base_manifest_path=base)
    def runner(_command: list[str], output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"%PDF-1.7\nexact")
    def verifier(*_args, **_kwargs) -> VerificationResult:
        return VerificationResult(ok=True, redline_hits=[], errors=[])
    finalize_job(job_id=job_id, private_root=root, profile_path=profile,
                 sources_path=sources, manifest_path=None, visual_approved=False,
                 runner=runner, verifier=verifier)
    (root / "generated" / job_id / "cv.pdf").write_bytes(b"changed")
    with pytest.raises(WorkflowInputError, match="artifact changed"):
        finalize_job(job_id=job_id, private_root=root, profile_path=profile,
                     sources_path=sources, manifest_path=None, visual_approved=True,
                     runner=runner, verifier=verifier)


def test_finalize_rejects_arbitrary_manifest_mismatch(tmp_path: Path) -> None:
    root, profile, sources, base, job_id = _prepared_inputs(tmp_path)
    assess_job(job_id=job_id, private_root=root, profile_path=profile,
               sources_path=sources, base_manifest_path=base)
    with pytest.raises(WorkflowInputError, match="tracked tailored manifest"):
        finalize_job(job_id=job_id, private_root=root, profile_path=profile,
                     sources_path=sources, manifest_path=base, visual_approved=False)


def test_actual_pinned_rendercv_e2e_uses_sanitized_private_fixture(tmp_path: Path) -> None:
    root, profile, sources, base, job_id = _prepared_inputs(tmp_path)
    assess_job(job_id=job_id, private_root=root, profile_path=profile,
               sources_path=sources, base_manifest_path=base)
    result = finalize_job(
        job_id=job_id,
        private_root=root,
        profile_path=profile,
        sources_path=sources,
        manifest_path=None,
        visual_approved=False,
    )
    pdf = root / "generated" / job_id / "cv.pdf"
    assert result.status == "visual_approval_required"
    assert pdf.read_bytes().startswith(b"%PDF")


def test_visual_approval_rejects_manifest_changed_after_render(tmp_path: Path) -> None:
    root, profile, sources, base, job_id = _prepared_inputs(tmp_path)
    assess_job(
        job_id=job_id,
        private_root=root,
        profile_path=profile,
        sources_path=sources,
        base_manifest_path=base,
    )

    def runner(_command: list[str], output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"%PDF-1.7\nexact")

    def verifier(*_args, **_kwargs) -> VerificationResult:
        return VerificationResult(ok=True, redline_hits=[], errors=[])

    finalize_job(
        job_id=job_id,
        private_root=root,
        profile_path=profile,
        sources_path=sources,
        manifest_path=None,
        visual_approved=False,
        runner=runner,
        verifier=verifier,
    )
    tracked = load_jobs(root / "tracker.yaml")[0]
    manifest = root / tracked.manifest_ref
    payload = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    payload["lines"] = payload["lines"][:1]
    manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkflowInputError, match="manifest changed"):
        finalize_job(
            job_id=job_id,
            private_root=root,
            profile_path=profile,
            sources_path=sources,
            manifest_path=None,
            visual_approved=True,
            runner=runner,
            verifier=verifier,
        )


def test_assess_rejects_requirements_changed_after_approval(tmp_path: Path) -> None:
    root, profile, sources, base, job_id = _prepared_inputs(tmp_path)
    requirements = root / "vacancies" / job_id / "requirements.yaml"
    payload = yaml.safe_load(requirements.read_text(encoding="utf-8"))
    payload["requirements"][0]["description"] = "Unapproved replacement requirement"
    requirements.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkflowInputError, match="approved requirements changed"):
        assess_job(
            job_id=job_id,
            private_root=root,
            profile_path=profile,
            sources_path=sources,
            base_manifest_path=base,
        )


def test_assess_rejects_snapshot_description_with_stale_digest(tmp_path: Path) -> None:
    root, profile, sources, base, job_id = _prepared_inputs(tmp_path)
    snapshot = root / "vacancies" / job_id / "snapshot.yaml"
    payload = yaml.safe_load(snapshot.read_text(encoding="utf-8"))
    payload["description"] = "Tampered vacancy description"
    snapshot.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkflowInputError, match="vacancy binding"):
        assess_job(
            job_id=job_id,
            private_root=root,
            profile_path=profile,
            sources_path=sources,
            base_manifest_path=base,
        )


def test_unresolved_hard_filter_blocks_assessment_and_rendering(tmp_path: Path) -> None:
    root, profile, sources, base, job_id = _prepared_inputs(
        tmp_path,
        "Requirements:\nMust be authorized to work in Exampleland",
    )
    with pytest.raises(WorkflowInputError, match="unresolved hard filters"):
        assess_job(
            job_id=job_id,
            private_root=root,
            profile_path=profile,
            sources_path=sources,
            base_manifest_path=base,
        )
    tracked = load_jobs(root / "tracker.yaml")[0]
    assert tracked.status == "approved"
    assert tracked.manifest_ref is None
