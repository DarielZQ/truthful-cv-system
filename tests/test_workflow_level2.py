from hashlib import sha256
from pathlib import Path
import subprocess

import yaml
import pytest

from truthful_cv.cli import main
from truthful_cv.ingestion import FetchOutcome
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


class _Fetcher:
    def __init__(self, outcome: FetchOutcome) -> None:
        self.outcome = outcome
        self.calls = 0

    def fetch(self, _url: str) -> FetchOutcome:
        self.calls += 1
        return self.outcome


def test_paste_ingestion_reserves_snapshot_requirements_and_tracker(tmp_path: Path) -> None:
    root = tmp_path / "private"
    result = ingest_vacancy(
        url="https://www.linkedin.com/jobs/view/123?tracking=secret",
        private_root=root,
        paste_text="Must provide Windows support to users. Fluent English required.",
        title="IT Support",
        employer="Example Corp",
        location="Costa Rica",
        external_id="123",
    )
    assert result.status == "requirements_review"
    assert result.job_id == "JOB-001"
    snapshot = root / "vacancies" / "JOB-001" / "snapshot.yaml"
    requirements = root / "vacancies" / "JOB-001" / "requirements.yaml"
    assert snapshot.exists() and requirements.exists()
    assert len(load_requirements(requirements)) >= 2
    tracked = load_jobs(root / "tracker.yaml")[0]
    assert tracked.status == "requirements_review"
    assert tracked.external_id == "123"


def test_blocked_ingestion_is_nonfatal_and_resumable(tmp_path: Path) -> None:
    root = tmp_path / "private"
    fetcher = _Fetcher(FetchOutcome(True, "access_blocked"))
    first = ingest_vacancy(
        url="https://careers.example.com/job/1?token=secret",
        private_root=root,
        fetcher=fetcher,
    )
    assert first.status == "paste_required"
    assert first.job_id == "JOB-001"
    assert fetcher.calls == 1
    second = ingest_vacancy(
        url="https://careers.example.com/job/1?token=secret",
        private_root=root,
        paste_text="Must support Windows users and document incidents.",
        title="Support",
        employer="Example",
    )
    assert second.job_id == first.job_id
    assert len(load_jobs(root / "tracker.yaml")) == 1


def test_public_ingestion_records_provider_for_validated_canonical_redirect(tmp_path: Path) -> None:
    body = b'''<script type="application/ld+json">{
      "@type":"JobPosting", "title":"Support", "hiringOrganization":{"name":"Example"},
      "description":"Provide Windows support to internal users."
    }</script>'''
    fetcher = _Fetcher(
        FetchOutcome(
            False,
            final_url="https://jobs.greenhouse.io/example/jobs/42",
            body=body,
            content_type="text/html",
        )
    )
    root = tmp_path / "private"
    job = ingest_vacancy(
        url="https://careers.example.com/job/42", private_root=root, fetcher=fetcher
    )
    snapshot = yaml.safe_load(
        (root / "vacancies" / job.job_id / "snapshot.yaml").read_text(encoding="utf-8")
    )
    assert snapshot["provider"] == "greenhouse"
    assert snapshot["canonical_url"] == "https://jobs.greenhouse.io/example/jobs/42"


def test_paste_ingestion_still_requires_https_url(tmp_path: Path) -> None:
    from truthful_cv.ingestion import UnsafeURLError

    with pytest.raises(UnsafeURLError):
        ingest_vacancy(
            url="file:///private/posting.txt",
            private_root=tmp_path / "private",
            paste_text="Must provide Windows support.",
            title="Support",
            employer="Example",
        )


def _write_profile(root: Path) -> tuple[Path, Path]:
    profile = root / "profile.yaml"
    sources = root / "sources.yaml"
    sources.write_text("schema_version: 1\nsources: [{id: SRC-001}]\n", encoding="utf-8")
    profile.write_text(
        """schema_version: 1
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
""",
        encoding="utf-8",
    )
    return profile, sources


def test_assess_requires_approval_and_writes_private_fit_report(tmp_path: Path) -> None:
    root = tmp_path / "private"
    ingested = ingest_vacancy(
        url="https://jobs.lever.co/example/42",
        private_root=root,
        paste_text="Must provide Windows support.",
        title="Support",
        employer="Example",
    )
    profile, sources = _write_profile(root)
    requirements_path = root / "vacancies" / ingested.job_id / "requirements.yaml"
    drafts = load_requirements(requirements_path)
    approve_job_requirements(
        job_id=ingested.job_id, private_root=root, approved_ids={item.id for item in drafts}
    )
    line = ContentLine(
        id="LINE-001", kind="summary", text="I support Windows users.", claim_ids=["CLM-001"]
    )
    signature = line_signature(line, load_profile(profile, sources), "english")
    profile.write_text(
        profile.read_text(encoding="utf-8") + f'approved_line_signatures: ["{signature}"]\n',
        encoding="utf-8",
    )
    base_manifest = root / "base-manifest.yaml"
    base_manifest.write_text(
        "schema_version: 1\nlanguage: english\nlines:\n"
        "  - {id: LINE-001, kind: summary, text: I support Windows users., claim_ids: [CLM-001]}\n",
        encoding="utf-8",
    )
    report = assess_job(
        job_id=ingested.job_id,
        private_root=root,
        profile_path=profile,
        sources_path=sources,
        base_manifest_path=base_manifest,
    )
    assert report.exists()
    data = yaml.safe_load(report.read_text(encoding="utf-8"))
    assert data["assessment"]["matches"][0]["claim_ids"] == ["CLM-001"]
    assert data["ranked_approved_claims"][0]["claim_id"] == "CLM-001"
    assert data["ranked_approved_lines"][0]["claim_id"] == "CLM-001"
    assert data["ranked_approved_lines"][0]["text"] == "I support Windows users."
    assert data["ranked_approved_lines"][0]["retrieval_score"] == pytest.approx(2 / 3)
    assert load_jobs(root / "tracker.yaml")[0].status == "assessed"


def test_assess_rejects_path_shaped_job_identifier_before_file_access(tmp_path: Path) -> None:
    with pytest.raises(WorkflowInputError, match="invalid job identifier"):
        assess_job(
            job_id="../../secret",
            private_root=tmp_path / "private",
            profile_path=tmp_path / "profile.yaml",
            sources_path=tmp_path / "sources.yaml",
            base_manifest_path=tmp_path / "manifest.yaml",
        )


def test_finalize_requires_visual_flag_then_copies_hash_identical_pdf(tmp_path: Path) -> None:
    root = tmp_path / "private"
    root.mkdir()
    profile, sources = _write_profile(root)
    line = ContentLine(
        id="LINE-001", kind="summary", text="I support Windows users.", claim_ids=["CLM-001"]
    )
    signature = line_signature(line, load_profile(profile, sources), "english")
    profile.write_text(
        profile.read_text(encoding="utf-8") + f'approved_line_signatures: ["{signature}"]\n',
        encoding="utf-8",
    )
    manifest = root / "manifest.yaml"
    manifest.write_text(
        """schema_version: 1
language: english
lines:
  - {id: LINE-001, kind: summary, text: I support Windows users., claim_ids: [CLM-001]}
""",
        encoding="utf-8",
    )
    # Reserve through ingestion so tracker and metadata exist.
    job = ingest_vacancy(
        url="https://jobs.lever.co/example/42",
        private_root=root,
        paste_text="Must provide Windows support.",
        title="Support: L1?",
        employer="Example/Corp",
    )
    requirements_path = root / "vacancies" / job.job_id / "requirements.yaml"
    approve_job_requirements(
        job_id=job.job_id,
        private_root=root,
        approved_ids={item.id for item in load_requirements(requirements_path)},
    )
    assess_job(
        job_id=job.job_id,
        private_root=root,
        profile_path=profile,
        sources_path=sources,
        base_manifest_path=manifest,
    )

    def runner(command: list[str], expected_pdf: Path) -> None:
        assert command[0]
        expected_pdf.parent.mkdir(parents=True, exist_ok=True)
        expected_pdf.write_bytes(b"%PDF-1.7\nsynthetic")

    def verifier(_path: Path, **_kwargs) -> VerificationResult:
        return VerificationResult(ok=True, redline_hits=[], errors=[])

    blocked = finalize_job(
        job_id=job.job_id,
        private_root=root,
        profile_path=profile,
        sources_path=sources,
        manifest_path=None,
        visual_approved=False,
        runner=runner,
        verifier=verifier,
    )
    assert blocked.status == "visual_approval_required"

    result = finalize_job(
        job_id=job.job_id,
        private_root=root,
        profile_path=profile,
        sources_path=sources,
        manifest_path=None,
        visual_approved=True,
        runner=runner,
        verifier=verifier,
    )
    assert result.deliverable is not None
    assert result.deliverable.name == "Example_Candidate_CV_Example_Corp_Support_L1_JOB-001.pdf"
    generated = root / "generated" / "JOB-001" / "cv.pdf"
    assert sha256(generated.read_bytes()).digest() == sha256(result.deliverable.read_bytes()).digest()
    assert load_jobs(root / "tracker.yaml")[0].status == "finalized"


def test_finalize_translates_renderer_failure_to_safe_workflow_error(tmp_path: Path) -> None:
    root = tmp_path / "private"
    root.mkdir()
    profile, sources = _write_profile(root)
    line = ContentLine(
        id="LINE-001", kind="summary", text="I support Windows users.", claim_ids=["CLM-001"]
    )
    signature = line_signature(line, load_profile(profile, sources), "english")
    profile.write_text(
        profile.read_text(encoding="utf-8") + f'approved_line_signatures: ["{signature}"]\n',
        encoding="utf-8",
    )
    manifest = root / "manifest.yaml"
    manifest.write_text(
        "schema_version: 1\nlanguage: english\nlines:\n"
        "  - {id: LINE-001, kind: summary, text: I support Windows users., claim_ids: [CLM-001]}\n",
        encoding="utf-8",
    )
    job = ingest_vacancy(
        url="https://jobs.lever.co/example/42",
        private_root=root,
        paste_text="Must provide Windows support.",
        title="Support",
        employer="Example",
    )
    requirements_path = root / "vacancies" / job.job_id / "requirements.yaml"
    approve_job_requirements(
        job_id=job.job_id,
        private_root=root,
        approved_ids={item.id for item in load_requirements(requirements_path)},
    )
    assess_job(
        job_id=job.job_id,
        private_root=root,
        profile_path=profile,
        sources_path=sources,
        base_manifest_path=manifest,
    )

    def failed_runner(_command: list[str], _expected_pdf: Path) -> None:
        raise subprocess.CalledProcessError(1, ["rendercv", str(root / "secret.yaml")])

    with pytest.raises(WorkflowInputError, match="renderer failed"):
        finalize_job(
            job_id=job.job_id,
            private_root=root,
            profile_path=profile,
            sources_path=sources,
            manifest_path=None,
            visual_approved=False,
            runner=failed_runner,
        )


def test_cli_protected_url_outputs_only_safe_paste_instruction(tmp_path: Path, capsys) -> None:
    secret_url = "https://www.linkedin.com/jobs/view/123?token=secret"
    code = main(["vacancy", "ingest", "--url", secret_url, "--private-root", str(tmp_path / "private")])
    output = capsys.readouterr()
    assert code == 0
    assert "paste_required" in output.out
    assert "--paste-file" in output.out
    assert "token=secret" not in output.out + output.err
    assert str(tmp_path) not in output.out + output.err


def test_cli_paste_file_failure_does_not_disclose_path(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "private" / "secret-description.txt"
    code = main(
        [
            "vacancy", "ingest", "--url", "https://jobs.lever.co/example/42",
            "--paste-file", str(missing), "--private-root", str(tmp_path / "private"),
            "--title", "Role", "--employer", "Example",
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "file not found" in captured.err
    assert str(tmp_path) not in captured.err


def test_cli_rejects_unsafe_url_without_echoing_it(tmp_path: Path, capsys) -> None:
    unsafe = "https://user:secret@127.0.0.1/private?token=secret"
    code = main(
        ["vacancy", "ingest", "--url", unsafe, "--private-root", str(tmp_path / "private")]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert captured.err == "validation error: unsafe vacancy URL\n"
    assert unsafe not in captured.err


def test_cli_approves_named_requirements_atomically(tmp_path: Path, capsys) -> None:
    root = tmp_path / "private"
    job = ingest_vacancy(
        url="https://jobs.lever.co/example/42",
        private_root=root,
        paste_text="Must provide Windows support.",
        title="Support",
        employer="Example",
    )
    requirements = root / "vacancies" / job.job_id / "requirements.yaml"
    ids = [item.id for item in load_requirements(requirements)]
    code = main(
        [
            "vacancy",
            "approve-requirements",
            "--job",
            job.job_id,
            "--private-root",
            str(root),
            "--approve",
            *ids,
        ]
    )
    assert code == 0
    assert all(item.review_status == "approved" for item in load_requirements(requirements))
    assert "approved requirements" in capsys.readouterr().out
