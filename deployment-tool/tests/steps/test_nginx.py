#!/usr/bin/env python3
"""Tests for Nginx TLS configuration step."""

import pytest

from octopize_avatar_deploy.steps import NginxTlsStep


class TestNginxTlsStep:
    """Test the NginxTlsStep."""

    @pytest.fixture
    def defaults(self):
        """Provide defaults with Nginx TLS paths."""
        return {
            "nginx": {
                "ssl_certificate_path": "./tls/server.fullchain.crt",
                "ssl_certificate_key_path": "./tls/private/server.decrypted.key",
            }
        }

    def test_collect_config_with_defaults(self, tmp_path, defaults):
        """Test that default values are used when not provided."""
        step = NginxTlsStep(tmp_path, defaults, config={}, interactive=False)

        result = step.collect_config()

        assert result["NGINX_SSL_CERTIFICATE_PATH"] == "./tls/server.fullchain.crt"
        assert result["NGINX_SSL_CERTIFICATE_KEY_PATH"] == "./tls/private/server.decrypted.key"

    def test_collect_config_overrides_defaults(self, tmp_path, defaults):
        """Test that provided values override defaults."""
        config = {
            "NGINX_SSL_CERTIFICATE_PATH": "/custom/cert.pem",
            "NGINX_SSL_CERTIFICATE_KEY_PATH": "/custom/key.pem",
        }
        step = NginxTlsStep(tmp_path, defaults, config=config, interactive=False)

        result = step.collect_config()

        assert result["NGINX_SSL_CERTIFICATE_PATH"] == "/custom/cert.pem"
        assert result["NGINX_SSL_CERTIFICATE_KEY_PATH"] == "/custom/key.pem"

    def test_step_metadata(self, tmp_path, defaults):
        """Test step metadata."""
        step = NginxTlsStep(tmp_path, defaults, config={}, interactive=False)

        assert step.name == "nginx_tls"
        assert step.required is True
        assert "nginx" in step.description.lower()
