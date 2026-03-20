"""Tests for topology-driven URL derivation."""

from octopize_avatar_deploy.topology_urls import (
    GenerateEnvTopology,
    ServiceLocation,
    resolve_host_client_storage_url,
    resolve_generate_env_urls,
)


def test_host_web_local_topology_uses_localhost_dev_url():
    """Host-run web should point at the local dev server by default."""
    resolved = resolve_generate_env_urls(
        GenerateEnvTopology(
            web_runtime=ServiceLocation.HOST,
            api_location=ServiceLocation.HOST,
            storage_location=ServiceLocation.HOST,
            sso_location=ServiceLocation.HOST,
        )
    )

    assert resolved.api_public_url == "http://localhost:8080/api"
    assert resolved.web_client_url == "http://localhost:3000"


def test_docker_web_local_topology_uses_gateway_web_url():
    """Docker-run web should keep the local gateway entrypoint."""
    resolved = resolve_generate_env_urls(
        GenerateEnvTopology(
            web_runtime=ServiceLocation.DOCKER,
            api_location=ServiceLocation.DOCKER,
            storage_location=ServiceLocation.HOST,
            sso_location=ServiceLocation.HOST,
        )
    )

    assert resolved.api_internal_url == "http://api:8000"
    assert resolved.web_client_url == "http://localhost:8080/web"


def test_external_public_base_derives_web_url_from_shared_base():
    """External/public topology should keep deriving the shared /web URL."""
    resolved = resolve_generate_env_urls(
        GenerateEnvTopology(
            web_runtime=ServiceLocation.HOST,
            api_location=ServiceLocation.EXTERNAL,
            storage_location=ServiceLocation.EXTERNAL,
            sso_location=ServiceLocation.EXTERNAL,
            public_base_url="https://avatar.example.com",
        )
    )

    assert resolved.api_public_url == "https://avatar.example.com/api"
    assert resolved.web_client_url == "https://avatar.example.com/web"


def test_host_client_storage_uses_direct_host_url_when_api_runs_on_host():
    """Host-side clients should talk to SeaweedFS directly for host-local API topologies."""
    topology = GenerateEnvTopology(
        api_runtime=ServiceLocation.HOST,
        api_location=ServiceLocation.HOST,
        storage_location=ServiceLocation.HOST,
        sso_location=ServiceLocation.HOST,
    )
    resolved = resolve_generate_env_urls(topology)

    assert resolve_host_client_storage_url(topology, resolved.storage_public_url) == (
        "http://localhost:8333"
    )


def test_host_client_storage_uses_gateway_when_api_is_docker_backed():
    """Host-side clients should keep the gateway URL when the API runs in Docker."""
    topology = GenerateEnvTopology(
        api_runtime=ServiceLocation.DOCKER,
        api_location=ServiceLocation.HOST,
        storage_location=ServiceLocation.DOCKER,
        sso_location=ServiceLocation.HOST,
    )
    resolved = resolve_generate_env_urls(topology)

    assert resolve_host_client_storage_url(topology, resolved.storage_public_url) == (
        "http://localhost:8080/storage"
    )


def test_host_client_storage_uses_shared_public_base_for_external_topology():
    """Host-side clients should derive storage from the shared public base when external."""
    topology = GenerateEnvTopology(
        api_location=ServiceLocation.EXTERNAL,
        storage_location=ServiceLocation.EXTERNAL,
        sso_location=ServiceLocation.EXTERNAL,
        public_base_url="https://avatar.example.com",
    )
    resolved = resolve_generate_env_urls(topology)

    assert resolve_host_client_storage_url(topology, resolved.storage_public_url) == (
        "https://avatar.example.com/storage"
    )
