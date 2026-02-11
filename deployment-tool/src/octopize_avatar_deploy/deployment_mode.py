"""Deployment mode enumeration."""

from enum import Enum


class DeploymentMode(Enum):
    """Enumeration for deployment modes."""

    PRODUCTION = "production"
    DEV = "dev"

    def __str__(self) -> str:
        """Return the string value of the mode."""
        return self.value
