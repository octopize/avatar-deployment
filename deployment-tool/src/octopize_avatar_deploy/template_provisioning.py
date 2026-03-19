"""Template provisioning helpers."""

from __future__ import annotations

from pathlib import Path

from octopize_avatar_deploy.download_templates import (
    GitHubTemplateProvider,
    LocalTemplateProvider,
    TemplateProvider,
    verify_required_files,
)
from octopize_avatar_deploy.printer import ConsolePrinter, Printer
from octopize_avatar_deploy.version_compat import (
    SCRIPT_VERSION,
    VersionError,
    validate_template_version,
)


class TemplateProvisioner:
    """Fetch and verify deployment templates without involving the full runner."""

    def __init__(
        self,
        output_dir: Path | str,
        template_from: str | Path = "github",
        verbose: bool = False,
        printer: Printer | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.template_from = str(template_from)
        self.verbose = verbose
        self.printer: Printer = printer or ConsolePrinter()
        self.templates_dir = self.output_dir / ".avatar-templates"
        self.template_source: Path | None = None
        self.template_provider = self._init_template_provider()

    def _init_template_provider(self) -> TemplateProvider:
        if self.template_from == "github":
            return GitHubTemplateProvider(branch="main", verbose=self.verbose)

        self.template_source = Path(self.template_from)
        return LocalTemplateProvider(source_dir=str(self.template_source), verbose=self.verbose)

    def ensure_templates(self) -> bool:
        """Ensure all required template files are available locally."""
        if self.template_source and not self.template_source.exists():
            self.printer.print_error(f"Template source directory not found: {self.template_source}")
            return False

        if self.template_from == "github":
            if self.template_provider.check_cached_templates(self.templates_dir):
                if self.verbose:
                    self.printer.print(f"Templates already cached in {self.templates_dir}/")
                return self._verify_templates()

            if self.verbose:
                self.printer.print("Downloading deployment templates from GitHub...")
        elif self.template_source and self.verbose:
            self.printer.print(f"Copying templates from {self.template_source}")

        success = self.template_provider.provide_all(self.templates_dir)
        if not success:
            if self.template_from == "github":
                self.printer.print_error("Failed to download templates from GitHub")
            else:
                self.printer.print_warning("Failed to copy some templates")
            return False

        return self._verify_templates()

    def _verify_templates(self) -> bool:
        """Verify the provisioned templates are complete and version-compatible."""
        if not self.templates_dir.exists():
            if self.verbose:
                self.printer.print_error(f"Templates directory not found: {self.templates_dir}")
            return False

        is_valid, error_message, total_files = verify_required_files(self.templates_dir)
        if not is_valid:
            if self.verbose and error_message:
                self.printer.print_error(error_message)
            return False

        if self.verbose:
            self.printer.print_success(f"Found all {total_files} required template files")

        return self._validate_template_version()

    def _validate_template_version(self) -> bool:
        """Validate template version compatibility."""
        version_file = self.templates_dir / ".template-version"

        if not version_file.exists():
            if self.verbose:
                self.printer.print_warning(
                    "No .template-version file found, skipping version check"
                )
            return True

        try:
            validate_template_version(
                version_file=version_file,
                script_version=SCRIPT_VERSION,
                verbose=self.verbose,
            )
            if self.verbose:
                self.printer.print_success(
                    f"Template version is compatible with script version {SCRIPT_VERSION}"
                )
            return True
        except VersionError as e:
            self.printer.print_error(str(e))
            return False
