"""Nginx TLS configuration step."""

from typing import Any

from .base import DeploymentStep, PromptConfig, parse_bool


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

        # Use generic prompt with boolean parser and yes/no prompt
        tls_enabled = self.get_config_or_prompt_generic(
            PromptConfig(
                config_key="NGINX_TLS_ENABLED",
                prompt_message="Enable TLS for Nginx?",
                default_value=default_tls_enabled,
                prompt_key="nginx_tls.enabled",
                prompt_function=self.prompt_yes_no,
                parse_and_validate=parse_bool,
            )
        )

        config["NGINX_TLS_ENABLED"] = tls_enabled

        if tls_enabled:
            cert_path = self.get_config_or_prompt_generic(
                PromptConfig(
                    config_key="NGINX_SSL_CERTIFICATE_PATH",
                    prompt_message="Path to TLS certificate (full chain)",
                    default_value=default_cert_path,
                    prompt_key="nginx_tls.ssl_certificate_path",
                )
            )

            key_path = self.get_config_or_prompt_generic(
                PromptConfig(
                    config_key="NGINX_SSL_CERTIFICATE_KEY_PATH",
                    prompt_message="Path to TLS private key (decrypted)",
                    default_value=default_key_path,
                    prompt_key="nginx_tls.ssl_certificate_key_path",
                )
            )

            config["NGINX_SSL_CERTIFICATE_PATH"] = cert_path
            config["NGINX_SSL_CERTIFICATE_KEY_PATH"] = key_path
        else:
            http_port = self.get_config_or_prompt_generic(
                PromptConfig(
                    config_key="NGINX_HTTP_PORT",
                    prompt_message="HTTP port for Nginx",
                    default_value=default_http_port,
                    prompt_key="nginx_tls.http_port",
                )
            )

            config["NGINX_HTTP_PORT"] = http_port
            config["NGINX_SSL_CERTIFICATE_PATH"] = "/dev/null"
            config["NGINX_SSL_CERTIFICATE_KEY_PATH"] = "/dev/null"

        return config

    def generate_secrets(self) -> dict[str, str]:
        """No secrets needed for Nginx TLS paths."""
        return {}
