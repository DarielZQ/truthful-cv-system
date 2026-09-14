import ipaddress
import http.client
import socket
import ssl
from dataclasses import dataclass
from typing import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit


from truthful_cv.providers import provider_policy, public_api_url


class UnsafeURLError(ValueError):
    """A URL does not meet the public HTTPS boundary."""


@dataclass(frozen=True)
class FetchResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True)
class FetchOutcome:
    paste_required: bool
    reason: str | None = None
    final_url: str | None = None
    body: bytes | None = None
    content_type: str | None = None


def validate_url_syntax(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise UnsafeURLError("only public HTTPS URLs are allowed")
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise UnsafeURLError("URL metadata is not allowed")
    try:
        port = parsed.port
    except ValueError as error:
        raise UnsafeURLError("invalid port") from error
    if port not in {None, 443}:
        raise UnsafeURLError("only port 443 is allowed")
    host = parsed.hostname.rstrip(".")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    raise UnsafeURLError("IP literal hosts are not allowed")


def _default_resolver(host: str) -> list[str]:
    return sorted({item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, pinned_ip: str, *, timeout: float) -> None:
        super().__init__(host, port=443, timeout=timeout, context=ssl.create_default_context())
        self.pinned_ip = pinned_ip

    def connect(self) -> None:
        raw_socket = socket.create_connection((self.pinned_ip, 443), self.timeout)
        self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)


def _default_transport(
    url: str, *, timeout: float, max_bytes: int, resolved_ip: str, hostname: str
) -> FetchResponse:
    parsed = urlsplit(url)
    target = parsed.path or "/"
    if parsed.query:
        target += "?" + parsed.query
    connection = _PinnedHTTPSConnection(hostname, resolved_ip, timeout=timeout)
    try:
        connection.request("GET", target, headers={"User-Agent": "truthful-cv/0.1 public-read"})
        response = connection.getresponse()
        return FetchResponse(response.status, dict(response.getheaders()), response.read(max_bytes + 1))
    finally:
        connection.close()


class SafeFetcher:
    def __init__(
        self,
        *,
        transport: Callable[..., FetchResponse] = _default_transport,
        resolver: Callable[[str], list[str]] = _default_resolver,
        timeout: float = 10.0,
        max_bytes: int = 2_000_000,
        max_redirects: int = 3,
        allow_public_hosts: set[str] | None = None,
    ) -> None:
        self.transport = transport
        self.resolver = resolver
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.allow_public_hosts = allow_public_hosts or set()

    def _validate_syntax(self, url: str) -> str:
        return validate_url_syntax(url)

    def _validate(self, url: str) -> list[str]:
        host = self._validate_syntax(url)
        try:
            addresses = self.resolver(host)
        except (OSError, socket.gaierror) as error:
            raise UnsafeURLError("host resolution failed") from error
        if not addresses:
            raise UnsafeURLError("host resolution returned no public addresses")
        for text in addresses:
            try:
                address = ipaddress.ip_address(text)
            except ValueError as error:
                raise UnsafeURLError("invalid DNS answer") from error
            if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
                address = address.ipv4_mapped
            if (
                not address.is_global
                or address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_reserved
                or address.is_multicast
                or address.is_unspecified
            ):
                raise UnsafeURLError("host does not resolve exclusively to public addresses")
        return addresses

    def fetch(self, url: str) -> FetchOutcome:
        self._validate_syntax(url)
        policy = provider_policy(url, self.allow_public_hosts)
        if policy.paste_required:
            return FetchOutcome(True, policy.reason)
        current = public_api_url(url) or url
        for hop in range(self.max_redirects + 1):
            current_policy = provider_policy(current, self.allow_public_hosts)
            if current_policy.paste_required and current == url:
                return FetchOutcome(True, current_policy.reason)
            addresses = self._validate(current)
            hostname = urlsplit(current).hostname or ""
            try:
                response = self.transport(
                    current,
                    timeout=self.timeout,
                    max_bytes=self.max_bytes,
                    resolved_ip=addresses[0],
                    hostname=hostname,
                )
            except (http.client.HTTPException, HTTPError, URLError, TimeoutError, OSError):
                return FetchOutcome(True, "network_error")
            headers = {key.lower(): value for key, value in response.headers.items()}
            if response.status in {301, 302, 303, 307, 308}:
                location = headers.get("location")
                if not location or hop >= self.max_redirects:
                    return FetchOutcome(True, "redirect_limit")
                target = urljoin(current, location)
                self._validate_syntax(target)
                target_policy = provider_policy(target, self.allow_public_hosts)
                if target_policy.paste_required:
                    return FetchOutcome(True, target_policy.reason)
                current = target
                continue
            if response.status in {401, 403, 429}:
                return FetchOutcome(True, "access_blocked")
            if response.status != 200:
                return FetchOutcome(True, "http_error")
            content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type not in {"text/html", "application/xhtml+xml", "application/json", "text/plain"}:
                return FetchOutcome(True, "unsupported_content_type")
            if len(response.body) > self.max_bytes:
                return FetchOutcome(True, "response_too_large")
            return FetchOutcome(False, final_url=current, body=response.body, content_type=content_type)
        return FetchOutcome(True, "redirect_limit")
