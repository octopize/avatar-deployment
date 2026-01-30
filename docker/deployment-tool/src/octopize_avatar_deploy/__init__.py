"""Octopize Avatar Deployment Tool."""

from .configure import DeploymentConfigurator, DeploymentRunner, main
from .printer import ConsolePrinter, Printer, SilentPrinter
from .version_compat import (
    SCRIPT_VERSION,
    VersionError,
    check_version_compatibility,
    validate_template_compatibility,
    validate_template_version,
)

__version__ = "0.1.0"
__all__ = [
    "main",
    "DeploymentRunner",
    "DeploymentConfigurator",
    "Printer",
    "ConsolePrinter",
    "SilentPrinter",
    "SCRIPT_VERSION",
    "VersionError",
    "check_version_compatibility",
    "validate_template_compatibility",
    "validate_template_version",
]
