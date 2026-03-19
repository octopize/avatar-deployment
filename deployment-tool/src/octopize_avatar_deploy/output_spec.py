"""Output specification for template rendering."""

from dataclasses import dataclass


@dataclass
class OutputSpec:
    """Specifies a template-to-output file mapping."""

    template_name: str  # e.g. "api.env.template"
    output_path: str  # e.g. "api/.env"
