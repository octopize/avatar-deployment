"""Topology-driven URL derivation helpers for generate-env."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

LOCAL_GATEWAY_BASE_URL = "http://localhost:8080"
LOCAL_API_URL = f"{LOCAL_GATEWAY_BASE_URL}/api"
LOCAL_STORAGE_URL = f"{LOCAL_GATEWAY_BASE_URL}/storage"
LOCAL_HOST_STORAGE_URL = "http://localhost:8333"
LOCAL_SSO_URL = f"{LOCAL_GATEWAY_BASE_URL}/sso"
LOCAL_DOCKER_WEB_URL = f"{LOCAL_GATEWAY_BASE_URL}/web"
LOCAL_HOST_WEB_URL = "http://localhost:3000"

DOCKER_API_URL = "http://api:8000"
DOCKER_STORAGE_URL = "http://s3:8333"


class ServiceLocation(StrEnum):
    """Where a generated component or dependency is reachable."""

    HOST = "host"
    DOCKER = "docker"
    EXTERNAL = "external"


@dataclass(frozen=True)
class GenerateEnvTopology:
    """Questionnaire answers that drive URL derivation."""

    api_runtime: ServiceLocation = ServiceLocation.HOST
    web_runtime: ServiceLocation = ServiceLocation.HOST
    api_location: ServiceLocation = ServiceLocation.HOST
    storage_location: ServiceLocation = ServiceLocation.HOST
    sso_location: ServiceLocation = ServiceLocation.HOST
    public_base_url: str | None = None

    def requires_public_base_url(self) -> bool:
        """Return whether any dependency requires a shared public base URL."""
        return any(
            location is ServiceLocation.EXTERNAL
            for location in (
                self.api_location,
                self.storage_location,
                self.sso_location,
            )
        )


@dataclass(frozen=True)
class ResolvedTopologyUrls:
    """Concrete URLs derived from the questionnaire result."""

    public_base_url: str
    public_domain: str
    api_public_url: str
    api_internal_url: str
    storage_public_url: str
    storage_internal_url: str
    sso_provider_url: str
    authentik_url: str
    web_client_url: str

    @property
    def sso_login_url(self) -> str:
        """Return the API SSO login URL derived from the public API URL."""
        return f"{self.api_public_url.rstrip('/')}/login/sso"


def normalize_base_url(value: str) -> str:
    """Normalize a base URL by trimming whitespace and trailing slashes."""
    return value.strip().rstrip("/")


def join_base_url(base_url: str, suffix: str) -> str:
    """Join a normalized base URL with a known suffix."""
    return f"{normalize_base_url(base_url)}{suffix}"


def public_base_url_from_service_url(service_url: str) -> str | None:
    """Return the scheme://netloc base for a service URL, if parseable."""
    parsed = urlsplit(service_url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc}"


def public_domain_from_url(url: str) -> str | None:
    """Return the host[:port] portion for a URL, if parseable."""
    parsed = urlsplit(url if "://" in url else f"https://{url}")
    if not parsed.hostname:
        return None
    host = parsed.hostname
    if parsed.port is not None:
        return f"{host}:{parsed.port}"
    return host


def parse_service_location(value: Any) -> ServiceLocation:
    """Parse a config or prompt value into a ServiceLocation enum."""
    if isinstance(value, ServiceLocation):
        return value

    normalized = str(value).strip().lower().replace("_", "-")
    aliases = {
        "host": ServiceLocation.HOST,
        "local": ServiceLocation.HOST,
        "local-host": ServiceLocation.HOST,
        "localhost": ServiceLocation.HOST,
        "docker": ServiceLocation.DOCKER,
        "same-docker-network": ServiceLocation.DOCKER,
        "external": ServiceLocation.EXTERNAL,
        "external-public": ServiceLocation.EXTERNAL,
        "public": ServiceLocation.EXTERNAL,
    }
    if normalized not in aliases:
        raise ValueError(
            f"Unknown topology location '{value}'. Expected one of: host, docker, external."
        )
    return aliases[normalized]


def resolve_generate_env_urls(topology: GenerateEnvTopology) -> ResolvedTopologyUrls:
    """Resolve public and internal URLs from the questionnaire answers."""
    public_base_url = normalize_base_url(topology.public_base_url or LOCAL_GATEWAY_BASE_URL)
    public_domain = public_domain_from_url(public_base_url)
    if public_domain is None:
        raise ValueError(f"Could not derive a public domain from '{public_base_url}'.")

    api_public_url = join_base_url(public_base_url, "/api")
    storage_public_url = join_base_url(public_base_url, "/storage")
    sso_provider_url = join_base_url(public_base_url, "/sso")
    web_client_url = (
        LOCAL_DOCKER_WEB_URL
        if topology.web_runtime is ServiceLocation.DOCKER and not topology.public_base_url
        else (
            LOCAL_HOST_WEB_URL
            if topology.web_runtime is ServiceLocation.HOST
            and not topology.requires_public_base_url()
            else join_base_url(public_base_url, "/web")
        )
    )

    api_internal_url = (
        DOCKER_API_URL
        if topology.web_runtime is ServiceLocation.DOCKER
        and topology.api_location is ServiceLocation.DOCKER
        else api_public_url
    )
    storage_internal_url = (
        DOCKER_STORAGE_URL
        if topology.api_runtime is ServiceLocation.DOCKER
        and topology.storage_location is ServiceLocation.DOCKER
        else storage_public_url
    )

    return ResolvedTopologyUrls(
        public_base_url=public_base_url,
        public_domain=public_domain,
        api_public_url=api_public_url,
        api_internal_url=api_internal_url,
        storage_public_url=storage_public_url,
        storage_internal_url=storage_internal_url,
        sso_provider_url=sso_provider_url,
        authentik_url=sso_provider_url,
        web_client_url=web_client_url,
    )


def resolve_host_client_storage_url(topology: GenerateEnvTopology, public_storage_url: str) -> str:
    """Return the default storage URL for host-side generated clients."""
    if topology.public_base_url or topology.requires_public_base_url():
        return public_storage_url

    if (
        topology.api_runtime is ServiceLocation.DOCKER
        or topology.api_location is ServiceLocation.DOCKER
    ):
        return LOCAL_STORAGE_URL

    return LOCAL_HOST_STORAGE_URL
