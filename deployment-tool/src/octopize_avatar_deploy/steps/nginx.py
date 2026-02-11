"""Nginx TLS configuration step."""

from typing import Any

from .base import DeploymentStep


class NginxTlsStep(DeploymentStep):
    """Handles Nginx TLS configuration."""

    name = "nginx_tls"
    description = "Configure Nginx TLS and HTTP settings"

    def collect_config(self) -> dict[str, Any]:
        """Collect Nginx TLS and HTTP configuration."""
        config: dict[str, Any] = {}

        default_tls_enabled = bool(self.get_default_value("nginx.tls_enabled"))
        default_http_port = str(self.get_default_value("nginx.http_port"))
        default_cert_path = self.get_default_value("nginx.ssl_certificate_path")
        default_key_path = self.get_default_value("nginx.ssl_certificate_key_path")

        if "NGINX_TLS_ENABLED" in self.config:
            tls_enabled = bool(self.config["NGINX_TLS_ENABLED"])
        elif self.interactive:
            tls_enabled = self.prompt_yes_no(
                "Enable TLS for Nginx?",
                default=default_tls_enabled,
                key="nginx_tls.enabled",
            )
        else:
            tls_enabled = default_tls_enabled

        config["NGINX_TLS_ENABLED"] = tls_enabled

        if tls_enabled:
            if "NGINX_SSL_CERTIFICATE_PATH" in self.config:
                cert_path = self.config["NGINX_SSL_CERTIFICATE_PATH"]
            elif self.interactive:
                cert_path = self.prompt(
                    "Path to TLS certificate (full chain)",
                    default=default_cert_path,
                    key="nginx_tls.ssl_certificate_path",
                )
            else:
                cert_path = default_cert_path

            if "NGINX_SSL_CERTIFICATE_KEY_PATH" in self.config:
                key_path = self.config["NGINX_SSL_CERTIFICATE_KEY_PATH"]
            elif self.interactive:
                key_path = self.prompt(
                    "Path to TLS private key (decrypted)",
                    default=default_key_path,
                    key="nginx_tls.ssl_certificate_key_path",
                )
            else:
                key_path = default_key_path

            config["NGINX_SSL_CERTIFICATE_PATH"] = cert_path
            config["NGINX_SSL_CERTIFICATE_KEY_PATH"] = key_path
        else:
            if "NGINX_HTTP_PORT" in self.config:
                http_port = str(self.config["NGINX_HTTP_PORT"])
            elif self.interactive:
                http_port = self.prompt(
                    "HTTP port for Nginx",
                    default=default_http_port,
                    key="nginx_tls.http_port",
                )
            else:
                http_port = default_http_port

            config["NGINX_HTTP_PORT"] = http_port
            config["NGINX_SSL_CERTIFICATE_PATH"] = "/dev/null"
            config["NGINX_SSL_CERTIFICATE_KEY_PATH"] = "/dev/null"

        return config

    def generate_secrets(self) -> dict[str, str]:
        """No secrets needed for Nginx TLS paths."""
        return {}
