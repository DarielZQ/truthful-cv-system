from datetime import UTC, datetime, timedelta
from http.client import BadStatusLine
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from truthful_cv.ingestion import FetchResponse, SafeFetcher
from truthful_cv.matcher import FitLevel, JobRequirement, assess_fit
from truthful_cv.models import Attribution, Claim, ClaimStatus, EvidenceTier
from truthful_cv.profile import Profile
from truthful_cv.providers import provider_policy
from truthful_cv.requirements import RequirementKind, extract_requirement_drafts
from truthful_cv.storage import safe_private_path
from truthful_cv.vacancy import extract_posting
from truthful_cv.workflow import _canonical_url
from truthful_cv.workflow import approve_job_requirements, ingest_vacancy
from truthful_cv.requirements import load_requirements


def _profile() -> Profile:
    claim = Claim.model_validate({
        "id": "CLM-001", "statement": "I support Windows users.",
        "category": "professional", "tier": EvidenceTier.C,
        "attribution": Attribution.INDIVIDUAL, "status": ClaimStatus.APPROVED,
        "source_ids": ["SRC-001"], "subject_id": "ROLE-001", "tags": ["windows"],
    })
    return Profile(schema_version=1, profile_id="example", claims=[claim], skills=[])


def test_canonical_url_keeps_semantic_query_and_drops_only_tracking() -> None:
    assert _canonical_url("https://EXAMPLE.com:443/job/?utm_source=x&jobId=42&fbclid=y&a=2") == (
        "https://example.com/job?jobId=42&a=2"
    )


def test_malformed_http_response_falls_back_without_traceback() -> None:
    def transport(*_args, **_kwargs):
        raise BadStatusLine("private-response-text")

    outcome = SafeFetcher(
        transport=transport,
        resolver=lambda _host: ["8.8.8.8"],
        allow_public_hosts={"careers.example.com"},
    ).fetch("https://careers.example.com/job")
    assert outcome.paste_required is True
    assert outcome.reason == "network_error"


def test_tag_overlap_machine_level_is_never_strong() -> None:
    requirement = JobRequirement(id="REQ-001", description="Windows", tags=["windows"])
    match = assess_fit(_profile(), [requirement]).matches[0]
    assert match.machine_level == FitLevel.PARTIAL


def test_personal_decisions_default_to_hard_filters_and_round_trip() -> None:
    drafts = extract_requirement_drafts("Requirements:\nMust be authorized to work here\nNight schedule")
    decisions = [item for item in drafts if item.kind in {RequirementKind.WORK_AUTHORIZATION, RequirementKind.SCHEDULE}]
    assert decisions and all(item.hard_filter for item in decisions)


def test_unpunctuated_requirement_sections_preserve_priority() -> None:
    drafts = extract_requirement_drafts(
        "Responsibilities\nHelp users\nRequirements\nWindows support\nEnglish\nPreferred\nITIL"
    )
    by_text = {item.description: item.priority.value for item in drafts}
    assert by_text["Help users"] == "informational"
    assert by_text["Windows support"] == "required"
    assert by_text["English"] == "required"
    assert by_text["ITIL"] == "preferred"


def test_jsonld_description_preserves_list_boundaries_and_valid_through() -> None:
    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    body = (f'''<script type="application/ld+json">{{"@type":"JobPosting","title":"Role",
      "hiringOrganization":{{"name":"Employer"}},"description":"<h2>Requirements</h2><ul><li>Windows</li><li>English</li></ul>",
      "validThrough":"{future}"}}</script>''').encode()
    posting = extract_posting(body, "text/html")
    assert posting.description == "Requirements\nWindows\nEnglish"
    assert posting.active is True


def test_interstitials_are_rejected_even_when_long() -> None:
    body = ("<html><body><h1>Verify you are human</h1><p>Cloudflare challenge cookie consent sign in " + "x " * 100 + "</p></body></html>").encode()
    with pytest.raises(ValueError, match="incomplete posting"):
        extract_posting(body, "text/html")


@pytest.mark.parametrize("url", [
    "https://linkedin.com/jobs/1", "https://indeed.com/viewjob?jk=1",
    "https://glassdoor.com/job/1", "https://acme.wd5.myworkdayjobs.com/job/1",
    "https://empleos.co.cr/job/1", "https://careers.example.com/job/1",
])
def test_paste_only_providers_never_call_network(url: str) -> None:
    called = False
    def transport(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError
    result = SafeFetcher(transport=transport, resolver=lambda _host: ["8.8.8.8"]).fetch(url)
    assert result.paste_required and not called


def test_explicit_allowed_public_host_uses_exact_match_only() -> None:
    assert provider_policy("https://careers.example.com/job", {"careers.example.com"}).paste_required is False
    assert provider_policy("https://evil.careers.example.com/job", {"careers.example.com"}).paste_required is True


def test_greenhouse_adapter_uses_documented_get_endpoint() -> None:
    calls = []
    def transport(url: str, **_kwargs) -> FetchResponse:
        calls.append(url)
        return FetchResponse(200, {"content-type": "application/json"}, b'{"id":42,"title":"Role","content":"<p>Windows support role</p>","company_name":"Acme"}')
    result = SafeFetcher(transport=transport, resolver=lambda _host: ["8.8.8.8"]).fetch(
        "https://boards.greenhouse.io/acme/jobs/42"
    )
    assert not result.paste_required
    assert calls == ["https://boards-api.greenhouse.io/v1/boards/acme/jobs/42"]


def test_lever_adapter_requests_json_with_get() -> None:
    calls = []
    def transport(url: str, **_kwargs) -> FetchResponse:
        calls.append(url)
        return FetchResponse(200, {"content-type": "application/json"}, b'{"id":"abc","text":"Role","descriptionPlain":"Windows support role","categories":{},"hostedUrl":"https://jobs.lever.co/acme/abc"}')
    result = SafeFetcher(transport=transport, resolver=lambda _host: ["8.8.8.8"]).fetch(
        "https://jobs.lever.co/acme/abc"
    )
    assert not result.paste_required
    assert calls == ["https://api.lever.co/v0/postings/acme/abc?mode=json"]


def test_safe_private_path_rejects_parent_and_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "private"
    root.mkdir()
    with pytest.raises(ValueError, match="boundary"):
        safe_private_path(root, "..", "outside")
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "generated"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        # Resolve is monkeypatched to model a junction/reparse escape where link creation is unavailable.
        original = Path.resolve
        def escaped(self: Path, strict: bool = False):
            if self == root / "generated" / "x.pdf":
                return outside / "x.pdf"
            return original(self, strict=strict)
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(Path, "resolve", escaped)
            with pytest.raises(ValueError, match="boundary"):
                safe_private_path(root, "generated", "x.pdf")
    else:
        with pytest.raises(ValueError, match="boundary"):
            safe_private_path(root, "generated", "x.pdf")


def test_mirrored_content_hash_deduplicates_before_writes(tmp_path: Path) -> None:
    root = tmp_path / "private"
    first = ingest_vacancy(url="https://one.example/job?jobId=1", private_root=root,
        paste_text="Requirements:\nWindows support", title="Role", employer="One")
    second = ingest_vacancy(url="https://two.example/job?jobId=2", private_root=root,
        paste_text="Requirements:\nWindows support", title="Role", employer="Two")
    assert second.job_id == first.job_id
    assert len(list((root / "vacancies").glob("JOB-*"))) == 1


def test_reingestion_does_not_regress_reviewed_job(tmp_path: Path) -> None:
    root = tmp_path / "private"
    first = ingest_vacancy(url="https://example.com/job?jobId=1", private_root=root,
        paste_text="Requirements:\nWindows support", title="Role", employer="One")
    requirement_path = root / "vacancies" / first.job_id / "requirements.yaml"
    approve_job_requirements(job_id=first.job_id, private_root=root,
        approved_ids={item.id for item in load_requirements(requirement_path)})
    before = requirement_path.read_bytes()
    second = ingest_vacancy(url="https://example.com/job?jobId=1&utm_source=x", private_root=root,
        paste_text="Requirements:\nChanged text", title="Changed", employer="Changed")
    assert second.status == "approved"
    assert requirement_path.read_bytes() == before


def test_repeated_blocked_ingestion_remains_idempotently_paste_required(tmp_path: Path) -> None:
    root = tmp_path / "private"
    first = ingest_vacancy(
        url="https://linkedin.com/jobs/123",
        private_root=root,
    )
    second = ingest_vacancy(
        url="https://linkedin.com/jobs/123",
        private_root=root,
    )
    assert first.status == second.status == "paste_required"
    assert first.job_id == second.job_id


def test_concurrent_mirrored_ingestion_recovers_one_identity(tmp_path: Path) -> None:
    root = tmp_path / "private"
    def ingest(index: int) -> str:
        return ingest_vacancy(
            url=f"https://mirror{index}.example/job?jobId={index}", private_root=root,
            paste_text="Requirements:\nSame Windows support posting", title="Role", employer="Acme"
        ).job_id
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(ingest, range(8)))
    assert set(ids) == {"JOB-001"}
