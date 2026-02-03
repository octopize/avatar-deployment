"""Nginx TLS configuration step."""

from typing import Any

from .base import DeploymentStep


class NginxTlsStep(DeploymentStep):
    """Handles Nginx TLS certificate path configuration."""

    name = "nginx_tls"
    description = "Configure Nginx TLS certificate paths"
    required = True

    def collect_config(self) -> dict[str, Any]:
        """Collect Nginx TLS certificate paths."""
        config: dict[str, Any] = {}

        defaults = self.defaults.get("nginx", {})
        default_cert_path = defaults.get(
            "ssl_certificate_path", "./tls/server.fullchain.crt"
        )
        default_key_path = defaults.get(
            "ssl_certificate_key_path", "./tls/private/server.decrypted.key"
        )

        if "NGINX_SSL_CERTIFICATE_PATH" in self.config:
            cert_path = self.config["NGINX_SSL_CERTIFICATE_PATH"]
        elif self.interactive:
            cert_path = self.prompt(
                "Path to TLS certificate (full chain)",
                default=default_cert_path,
            )
        else:
            cert_path = default_cert_path

        if "NGINX_SSL_CERTIFICATE_KEY_PATH" in self.config:
            key_path = self.config["NGINX_SSL_CERTIFICATE_KEY_PATH"]
        elif self.interactive:
            key_path = self.prompt(
                "Path to TLS private key (decrypted)",
                default=default_key_path,
            )
        else:
            key_path = default_key_path

        config["NGINX_SSL_CERTIFICATE_PATH"] = cert_path
        config["NGINX_SSL_CERTIFICATE_KEY_PATH"] = key_path

        return config

    def generate_secrets(self) -> dict[str, str]:
        """No secrets needed for Nginx TLS paths."""
        return {}
