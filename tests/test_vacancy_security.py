from pathlib import Path

import pytest

from truthful_cv.ingestion import FetchResponse, SafeFetcher, UnsafeURLError
from truthful_cv.providers import Provider, classify_provider, provider_policy
from truthful_cv.vacancy import AcquisitionMode, VacancySnapshot, save_snapshot


@pytest.mark.parametrize(
    ("url", "provider"),
    [
        ("https://www.linkedin.com/jobs/view/123", Provider.LINKEDIN),
        ("https://uk.indeed.co.uk/viewjob?jk=42", Provider.INDEED),
        ("https://jobs.greenhouse.io/acme/jobs/42", Provider.GREENHOUSE),
        ("https://boards.greenhouse.io/acme/jobs/42", Provider.GREENHOUSE),
        ("https://jobs.lever.co/acme/abc", Provider.LEVER),
        ("https://acme.wd5.myworkdayjobs.com/en-US/site/job/role_R1", Provider.WORKDAY),
        ("https://acme.wd1.myworkdaysite.com/recruiting/site/job/role_R1", Provider.WORKDAY),
        ("https://empleos.co.cr/job/1", Provider.COSTA_RICA_PORTAL),
        ("https://careers.example.com/job/1", Provider.EMPLOYER),
    ],
)
def test_provider_classification_uses_exact_suffix_boundaries(url: str, provider: Provider) -> None:
    assert classify_provider(url) == provider


def test_protected_networks_always_require_paste_without_transport_call() -> None:
    called = False

    def transport(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("must not call network")

    result = provider_policy("https://evil.linkedin.com.example/jobs/1")
    assert result.provider == Provider.EMPLOYER
    blocked = provider_policy("https://www.indeed.com/viewjob?jk=secret")
    assert blocked.paste_required is True

    fetcher = SafeFetcher(transport=transport, resolver=lambda _host: ["8.8.8.8"])
    outcome = fetcher.fetch("https://www.glassdoor.com/job-listing/1")
    assert outcome.paste_required
    assert not called


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/job",
        "https://user:pass@example.com/job",
        "https://example.com:444/job",
        "https://127.0.0.1/job",
        "https://[::1]/job",
        "https://example.com/job#fragment",
    ],
)
def test_ssrf_boundary_rejects_unsafe_url_before_transport(url: str) -> None:
    fetcher = SafeFetcher(
        transport=lambda *_args, **_kwargs: pytest.fail("transport called"),
        resolver=lambda _host: ["8.8.8.8"],
    )
    with pytest.raises(UnsafeURLError):
        fetcher.fetch(url)


@pytest.mark.parametrize("address", ["10.0.0.1", "169.254.1.2", "::1", "::ffff:127.0.0.1", "224.0.0.1"])
def test_ssrf_boundary_rejects_non_global_dns_answers(address: str) -> None:
    fetcher = SafeFetcher(
        transport=lambda *_args, **_kwargs: pytest.fail("transport called"),
        resolver=lambda _host: [address],
        allow_public_hosts={"careers.example.com"},
    )
    with pytest.raises(UnsafeURLError):
        fetcher.fetch("https://careers.example.com/job")


def test_redirects_are_manually_validated_and_capped() -> None:
    calls: list[str] = []

    def transport(url: str, **_kwargs) -> FetchResponse:
        calls.append(url)
        return FetchResponse(302, {"location": "https://127.0.0.1/secret"}, b"")

    fetcher = SafeFetcher(
        transport=transport,
        resolver=lambda _host: ["8.8.8.8"],
        allow_public_hosts={"careers.example.com"},
    )
    with pytest.raises(UnsafeURLError):
        fetcher.fetch("https://careers.example.com/job")
    assert len(calls) == 1


def test_redirect_to_protected_provider_stops_before_resolving_target() -> None:
    resolved: list[str] = []

    def resolver(host: str) -> list[str]:
        resolved.append(host)
        return ["8.8.8.8"]

    fetcher = SafeFetcher(
        transport=lambda *_args, **_kwargs: FetchResponse(
            302, {"location": "https://www.linkedin.com/jobs/view/42"}, b""
        ),
        resolver=resolver,
        allow_public_hosts={"careers.example.com"},
    )
    outcome = fetcher.fetch("https://careers.example.com/job")
    assert outcome.paste_required
    assert resolved == ["careers.example.com"]


def test_fetch_enforces_content_type_and_size() -> None:
    fetcher = SafeFetcher(
        transport=lambda *_args, **_kwargs: FetchResponse(
            200, {"content-type": "text/html; charset=utf-8"}, b"x" * 101
        ),
        resolver=lambda _host: ["8.8.8.8"],
        max_bytes=100,
        allow_public_hosts={"careers.example.com"},
    )
    result = fetcher.fetch("https://careers.example.com/job")
    assert result.paste_required
    assert result.reason == "response_too_large"


def test_snapshot_write_is_atomic_private_and_contains_no_raw_response(tmp_path: Path) -> None:
    private = tmp_path / "private"
    snapshot = VacancySnapshot(
        job_id="JOB-001",
        source_url="https://careers.example.com/jobs/1?source=mail",
        canonical_url="https://careers.example.com/jobs/1",
        provider=Provider.EMPLOYER,
        acquisition_mode=AcquisitionMode.USER_PASTE,
        retrieved_at="2026-09-13T12:00:00Z",
        title="Support Specialist",
        employer="Example Corp",
        location="Costa Rica",
        description="Provide technical support.",
        content_hash="sha256:" + "a" * 64,
        policy_reason="user_paste",
    )
    output = save_snapshot(private, snapshot)
    assert output == private / "vacancies" / "JOB-001" / "snapshot.yaml"
    text = output.read_text(encoding="utf-8")
    assert "<script" not in text
    assert "cookies" not in text


def test_snapshot_rejects_symlink_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    private = tmp_path / "private"
    private.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = True
    try:
        (private / "vacancies").symlink_to(outside, target_is_directory=True)
    except OSError:
        linked = False
    snapshot = VacancySnapshot(
        job_id="JOB-001", source_url="https://example.com/1", canonical_url="https://example.com/1",
        provider=Provider.EMPLOYER, acquisition_mode=AcquisitionMode.USER_PASTE,
        retrieved_at="2026-09-13T12:00:00Z", title="Role", employer="Employer",
        description="A sufficiently useful description.", content_hash="sha256:" + "b" * 64,
        policy_reason="user_paste",
    )
    if not linked:
        original = Path.resolve
        target = private / "vacancies" / "JOB-001" / "snapshot.yaml"
        def escaped(self: Path, strict: bool = False) -> Path:
            if self == target:
                return outside / "JOB-001" / "snapshot.yaml"
            return original(self, strict=strict)
        monkeypatch.setattr(Path, "resolve", escaped)
    with pytest.raises(ValueError, match="private storage boundary"):
        save_snapshot(private, snapshot)
