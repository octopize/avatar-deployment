"""
Example of using the new modular step system in configure.py

This shows how to register and execute component-based steps.
"""

from pathlib import Path

from steps import (
    DatabaseStep,
    EmailStep,
    RequiredConfigStep,
    StorageStep,
    TelemetryStep,
)
from version_compat import check_compatibility, get_template_version

# Script version
SCRIPT_VERSION = "0.1.0"


def run_deployment(output_dir: Path, defaults: dict, interactive: bool = True):
    """
    Execute deployment with modular steps.

    Args:
        output_dir: Output directory
        defaults: Loaded defaults from defaults.yaml
        interactive: Whether to run interactively
    """
    # Check version compatibility
    template_dir = output_dir / ".avatar-templates"
    template_version = get_template_version(template_dir)
    if template_version:
        check_compatibility(SCRIPT_VERSION, template_version, strict=True)

    # Initialize configuration
    config = {}
    all_secrets = {}

    # Define steps in order
    step_classes = [
        RequiredConfigStep,  # PUBLIC_URL, ENV_NAME, versions
        EmailStep,           # Email provider, SMTP config + credentials
        DatabaseStep,        # Database config + passwords
        TelemetryStep,       # Sentry, telemetry, logging
        StorageStep,         # Storage + app secrets
    ]

    # Create step names for state manager
    step_names = [cls.name for cls in step_classes]

    # Initialize state manager with dynamic steps
    from octopize_avatar_deploy.state_manager import DeploymentState

    state_file = output_dir / ".deployment-state.yaml"
    state = DeploymentState(state_file, steps=step_names)

    # Execute each step
    for step_class in step_classes:
        step_name = step_class.name

        # Check if already completed
        if state.get_step_status(step_name) == "completed":
            print(f"✓ {step_class.description} (already completed)")
            continue

        # Mark as started
        state.mark_step_started(step_name)

        # Execute step
        print(f"\n{'='*60}")
        print(f"Step: {step_class.description}")
        print(f"{'='*60}")

        step = step_class(
            config=config,
            output_dir=output_dir,
            defaults=defaults,
            interactive=interactive
        )

        result = step.execute()

        # Update config and secrets
        config.update(result["config"])
        all_secrets.update(step.secrets)

        # Save secrets
        secrets_dir = output_dir / ".secrets"
        step.save_secrets(secrets_dir)

        # Save state
        state.state["config"].update(result["config"])
        state.state["step_data"][step_name] = result
        state.mark_step_completed(step_name)
        state.save()

        print(f"✓ {step_class.description} completed")

    # Render templates
    print(f"\n{'='*60}")
    print("Generating configuration files...")
    print(f"{'='*60}")

    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(template_dir))

    # Render .env
    template = env.get_template(".env.template")
    rendered = template.render(**config)
    (output_dir / ".env").write_text(rendered)
    print(f"✓ Generated {output_dir / '.env'}")

    # Render nginx.conf
    template = env.get_template("nginx.conf.template")
    rendered = template.render(**config)
    (output_dir / "nginx.conf").write_text(rendered)
    print(f"✓ Generated {output_dir / 'nginx.conf'}")

    # Clean up state file on success
    state.state_file.unlink(missing_ok=True)

    print(f"\n{'='*60}")
    print("✅ Deployment configuration completed!")
    print(f"{'='*60}")
    print(f"\nConfiguration files generated in: {output_dir}")
    print(f"Secrets stored in: {output_dir / '.secrets'}")
    print("\nNext steps:")
    print(f"  1. Review generated files: {output_dir / '.env'}")
    print("  2. Start services: docker-compose up -d")


if __name__ == "__main__":
    # Example usage
    import yaml

    output_dir = Path("/tmp/avatar-test")
    output_dir.mkdir(exist_ok=True)

    # Load defaults
    defaults_path = Path(__file__).parent / "src" / "octopize_avatar_deploy" / "defaults.yaml"
    with open(defaults_path) as f:
        defaults = yaml.safe_load(f)

    run_deployment(output_dir, defaults, interactive=False)
