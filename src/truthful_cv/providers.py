from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import quote, urlsplit


class Provider(StrEnum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GLASSDOOR = "glassdoor"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    COSTA_RICA_PORTAL = "costa_rica_portal"
    EMPLOYER = "employer"


@dataclass(frozen=True)
class ProviderPolicy:
    provider: Provider
    paste_required: bool
    reason: str | None = None


def _host_matches(host: str, suffix: str) -> bool:
    return host == suffix or host.endswith("." + suffix)


def classify_provider(url: str) -> Provider:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    if _host_matches(host, "linkedin.com"):
        return Provider.LINKEDIN
    indeed_domains = {
        "indeed.com",
        "indeed.co.uk",
        "indeed.ca",
        "indeed.de",
        "indeed.fr",
        "indeed.co.in",
        "indeed.com.au",
        "indeed.nl",
        "indeed.es",
        "indeed.co.cr",
    }
    if any(_host_matches(host, domain) for domain in indeed_domains):
        return Provider.INDEED
    if _host_matches(host, "glassdoor.com"):
        return Provider.GLASSDOOR
    if _host_matches(host, "greenhouse.io"):
        return Provider.GREENHOUSE
    if _host_matches(host, "lever.co"):
        return Provider.LEVER
    if _host_matches(host, "myworkdayjobs.com") or _host_matches(host, "myworkdaysite.com"):
        return Provider.WORKDAY
    if host.endswith(".co.cr") or host.endswith(".cr"):
        return Provider.COSTA_RICA_PORTAL
    return Provider.EMPLOYER


def public_api_url(url: str) -> str | None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    parts = [quote(part, safe="") for part in parsed.path.split("/") if part]
    if _host_matches(host, "greenhouse.io") and len(parts) >= 3 and parts[-2] == "jobs":
        return f"https://boards-api.greenhouse.io/v1/boards/{parts[-3]}/jobs/{parts[-1]}"
    if host == "jobs.lever.co" and len(parts) >= 2:
        return f"https://api.lever.co/v0/postings/{parts[0]}/{parts[1]}?mode=json"
    return None


def provider_policy(url: str, allow_public_hosts: set[str] | None = None) -> ProviderPolicy:
    provider = classify_provider(url)
    if provider in {Provider.LINKEDIN, Provider.INDEED, Provider.GLASSDOOR}:
        return ProviderPolicy(provider, True, "protected_provider")
    if provider in {Provider.WORKDAY, Provider.COSTA_RICA_PORTAL}:
        return ProviderPolicy(provider, True, "paste_only_provider")
    if provider in {Provider.GREENHOUSE, Provider.LEVER}:
        return ProviderPolicy(provider, public_api_url(url) is None, "unrecognized_provider_url")
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    allowed = {item.lower().rstrip(".") for item in allow_public_hosts or set()}
    if host not in allowed:
        return ProviderPolicy(provider, True, "public_host_not_allowed")
    return ProviderPolicy(provider, False)
