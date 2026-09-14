import html as html_module
import json
import os
import re
from datetime import UTC, datetime
from enum import StrEnum
from html.parser import HTMLParser
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, Field

from truthful_cv.providers import Provider
from truthful_cv.storage import safe_private_path


class AcquisitionMode(StrEnum):
    PUBLIC_URL = "public_url"
    USER_PASTE = "user_paste"


class VacancySnapshot(BaseModel):
    schema_version: int = 1
    job_id: str = Field(pattern=r"^JOB-\d{3,}$")
    source_url: str
    canonical_url: str
    provider: Provider
    external_id: str | None = None
    acquisition_mode: AcquisitionMode
    retrieved_at: str
    title: str = Field(min_length=1)
    employer: str = Field(min_length=1)
    location: str | None = None
    posted_at: str | None = None
    active: bool | None = None
    description: str = Field(min_length=10)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    policy_reason: str


class ExtractedPosting(BaseModel):
    title: str
    employer: str
    description: str
    location: str | None = None
    external_id: str | None = None
    posted_at: str | None = None
    active: bool | None = None


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hidden = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        elif tag in {"p", "li", "div", "h1", "h2", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1
        elif tag in {"p", "li", "div", "h1", "h2"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _plain(value: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html_module.unescape(value))
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line)


def _active_until(value: object) -> bool | None:
    if not value:
        return None
    try:
        normalized = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC) >= datetime.now(UTC)
    except ValueError:
        return None


def _jobposting(value: object) -> dict | None:
    if isinstance(value, list):
        for item in value:
            found = _jobposting(item)
            if found:
                return found
    if isinstance(value, dict):
        types = value.get("@type")
        if types == "JobPosting" or isinstance(types, list) and "JobPosting" in types:
            return value
        for key in ("@graph", "mainEntity"):
            found = _jobposting(value.get(key))
            if found:
                return found
    return None


def extract_posting(body: bytes, content_type: str) -> ExtractedPosting:
    text = body.decode("utf-8", errors="strict")
    if content_type == "application/json":
        payload = json.loads(text)
        if isinstance(payload, dict) and payload.get("title") and payload.get("content"):
            absolute_parts = urlsplit(str(payload.get("absolute_url", ""))).path.strip("/").split("/")
            inferred_employer = absolute_parts[0] if absolute_parts and absolute_parts[0] else ""
            return ExtractedPosting(
                title=_plain(str(payload["title"])),
                employer=_plain(str(payload.get("company_name") or payload.get("companyName") or inferred_employer)),
                description=_plain(str(payload["content"])),
                location=_plain(str((payload.get("location") or {}).get("name", ""))) or None,
                external_id=str(payload.get("id")) if payload.get("id") is not None else None,
            )
        if isinstance(payload, dict) and payload.get("text") and (payload.get("descriptionPlain") or payload.get("description")):
            categories = payload.get("categories") if isinstance(payload.get("categories"), dict) else {}
            hosted = urlsplit(str(payload.get("hostedUrl", ""))).path.strip("/").split("/")
            employer = hosted[0] if hosted and hosted[0] else str(payload.get("company", ""))
            return ExtractedPosting(
                title=_plain(str(payload["text"])), employer=employer,
                description=_plain(str(payload.get("descriptionPlain") or payload.get("description"))),
                location=_plain(str(categories.get("location", ""))) or None,
                external_id=str(payload.get("id")) if payload.get("id") is not None else None,
            )
        candidates = [text]
    else:
        candidates = re.findall(
            r"<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
            text,
            flags=re.I | re.S,
        )
    for candidate in candidates:
        try:
            posting = _jobposting(json.loads(html_module.unescape(candidate)))
        except (json.JSONDecodeError, TypeError):
            continue
        if not posting:
            continue
        organization = posting.get("hiringOrganization")
        employer = organization.get("name") if isinstance(organization, dict) else organization
        location_data = posting.get("jobLocation")
        if isinstance(location_data, list):
            location_data = location_data[0] if location_data else None
        address = location_data.get("address") if isinstance(location_data, dict) else None
        if isinstance(address, dict):
            location = ", ".join(
                str(address[key]) for key in ("addressLocality", "addressRegion", "addressCountry") if address.get(key)
            ) or None
        else:
            location = None
        identifier = posting.get("identifier")
        external_id = identifier.get("value") if isinstance(identifier, dict) else identifier
        description = _plain(str(posting.get("description", "")))
        title = _plain(str(posting.get("title", "")))
        employer = _plain(str(employer or ""))
        if title and employer and len(description) >= 20:
            return ExtractedPosting(
                title=title,
                employer=employer,
                description=description,
                location=location,
                external_id=str(external_id) if external_id else None,
                posted_at=str(posting.get("datePosted")) if posting.get("datePosted") else None,
                active=_active_until(posting.get("validThrough")),
            )
    parser = _VisibleTextParser()
    parser.feed(text)
    visible = "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())
    lowered = visible.casefold()
    interstitials = (
        "please log in", "sign in", "captcha", "access denied", "cookie consent",
        "verify you are human", "verify human", "cloudflare", "bot challenge", "challenge-platform",
    )
    if len(visible) < 100 or any(marker in lowered for marker in interstitials):
        raise ValueError("incomplete posting; paste required")
    title_match = re.search(r"<h1\b[^>]*>(.*?)</h1>", text, re.I | re.S)
    title = _plain(title_match.group(1)) if title_match else ""
    employer_match = re.search(r"(?:company|employer)[\s:]+([^\n<]+)", visible, re.I)
    employer = employer_match.group(1).strip() if employer_match else ""
    posting_signals = ("requirements", "required", "responsibilities", "qualifications", "requisitos")
    if not title or not employer or not any(signal in lowered for signal in posting_signals):
        raise ValueError("incomplete posting; paste required")
    return ExtractedPosting(title=title, employer=employer, description=visible)


def _atomic_yaml(path: Path, data: dict) -> None:
    temporary_name: str | None = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".snapshot.", suffix=".tmp", delete=False
        ) as temporary:
            yaml.safe_dump(data, temporary, sort_keys=False, allow_unicode=True)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name and Path(temporary_name).exists():
            Path(temporary_name).unlink()


def save_snapshot(private_root: Path, snapshot: VacancySnapshot) -> Path:
    root = private_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = safe_private_path(root, "vacancies", snapshot.job_id, "snapshot.yaml")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination = safe_private_path(root, "vacancies", snapshot.job_id, "snapshot.yaml")
    _atomic_yaml(destination, snapshot.model_dump(mode="json"))
    return destination


def load_snapshot(private_root: Path, job_id: str) -> VacancySnapshot:
    if not __import__("re").fullmatch(r"JOB-\d{3,}", job_id):
        raise ValueError("invalid job identifier")
    path = safe_private_path(private_root, "vacancies", job_id, "snapshot.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return VacancySnapshot.model_validate(data)
