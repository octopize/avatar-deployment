"""CLI entry point for authentik-blueprint tools."""

import argparse
import sys
from pathlib import Path


def main():
    """Main CLI entry point with subcommands."""
    parser = argparse.ArgumentParser(
        prog="authentik-blueprint",
        description="Authentik blueprint tools - export and validate blueprints"
    )
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Export subcommand
    export_parser = subparsers.add_parser(
        'export',
        help='Convert blueprint from PK references to !Find lookups'
    )
    export_parser.add_argument(
        "input",
        type=Path,
        help="Input blueprint YAML file (with PKs)"
    )
    export_parser.add_argument(
        "output",
        type=Path,
        help="Output blueprint YAML file (with !Find)"
    )
    export_parser.add_argument(
        "--validate",
        action="store_true",
        help="Run validation on output"
    )
    export_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    export_parser.add_argument(
        "--jinja2",
        "-j",
        action="store_true",
        help="Generate Jinja2 template format (converts [[PLACEHOLDER]] to {{ BLUEPRINT_PLACEHOLDER }})"
    )

    # Validate subcommand
    validate_parser = subparsers.add_parser(
        'validate',
        help='Validate blueprint template'
    )
    validate_parser.add_argument(
        "blueprint",
        type=Path,
        help="Path to blueprint file to validate"
    )

    args = parser.parse_args()

    # Show help if no command specified
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to appropriate handler
    if args.command == 'export':
        return export_command(
            input=args.input,
            output=args.output,
            validate=args.validate,
            verbose=args.verbose,
            jinja2=args.jinja2
        )
    elif args.command == 'validate':
        return validate_command(blueprint=args.blueprint)


def export_command(input: Path, output: Path, validate: bool, verbose: bool, jinja2: bool):
    """Handle export command."""
    from .converter import BlueprintConverter
    from .validator import BlueprintValidator

    # Validate inputs
    if not input.exists():
        print(f"❌ Input file not found: {input}", file=sys.stderr)
        sys.exit(1)

    # If jinja2 mode is enabled, ensure output has .j2 suffix
    output_path = output
    if jinja2 and not str(output_path).endswith('.j2'):
        print("⚠️  Warning: Jinja2 mode enabled but output doesn't end in .j2")
        print(f"   Suggested: {output_path}.j2")
        output_path = output_path.with_suffix(output_path.suffix + '.j2')

    # Convert blueprint
    converter = BlueprintConverter(verbose=verbose)

    try:
        blueprint = converter.load_blueprint(input)
        converted = converter.convert_blueprint(blueprint, jinja2=jinja2)
        converter.save_blueprint(converted, output_path, jinja2=jinja2)

        print(f"\n✅ Conversion complete: {output_path}")
        print(f"   Processed {len(converted.get('entries', []))} entries")

    except Exception as e:
        print(f"❌ Conversion failed: {e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    # Optionally validate
    if validate:
        print(f"\n{'='*60}")
        print("Running validation...")
        print(f"{'='*60}\n")

        validator = BlueprintValidator()
        if not validator.validate(output_path):
            sys.exit(1)


def validate_command(blueprint: Path):
    """Handle validate command."""
    from .validator import BlueprintValidator

    if not blueprint.exists():
        print(f"❌ Blueprint file not found: {blueprint}", file=sys.stderr)
        sys.exit(1)

    validator = BlueprintValidator()
    if not validator.validate(blueprint):
        sys.exit(1)


if __name__ == "__main__":
    main()
