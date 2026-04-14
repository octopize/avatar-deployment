"""CLI entry point for authentik-blueprint tools.

Subcommands
-----------
export          Convert a raw Authentik blueprint export (with PK references)
                into a portable declarative blueprint using !Find lookups.
                Run this once when capturing a new blueprint from the UI.

validate        Fast static checks on a blueprint template: no raw PKs, no
                managed flags, no UUIDs, no undocumented placeholders, and
                known single-choice field values are valid.
                Run this on every commit — it needs no network or containers.

schema-check    Validate all single-choice field values against the actual
                Authentik source tree. More comprehensive than `validate`:
                covers all 65+ TextChoices fields across the codebase rather
                than only the fields listed in KNOWN_FIELD_CHOICES.
                Requires git (shallow-clones the Authentik repo; cached in
                /tmp/authentik-<version>) but no running containers.
                Run this when bumping the Authentik version or after editing
                model-constrained fields in the blueprint.

verify-live     Run the entry-by-entry importer stepper inside a running
                Authentik worker (Docker or Kubernetes) and fail if any entry
                is rejected. This is the definitive check — it exercises the
                real serializers and catches errors that static analysis cannot:
                broken !KeyOf references, FK failures, uniqueness violations,
                and policy expression errors.
                Run this after `run-noninteractive-local.sh` during development,
                and after every deployment to staging/production.
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        prog="authentik-blueprint",
        description="Authentik blueprint tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # ------------------------------------------------------------------
    # export
    # ------------------------------------------------------------------
    export_parser = subparsers.add_parser(
        "export",
        help="Convert a raw blueprint export (PK refs) to declarative !Find lookups",
    )
    export_parser.add_argument("input", type=Path, help="Input blueprint YAML (with PKs)")
    export_parser.add_argument("output", type=Path, help="Output blueprint YAML (with !Find)")
    export_parser.add_argument(
        "--validate", action="store_true", help="Run `validate` on the output after conversion"
    )
    export_parser.add_argument("--verbose", "-v", action="store_true")

    # ------------------------------------------------------------------
    # validate
    # ------------------------------------------------------------------
    validate_parser = subparsers.add_parser(
        "validate",
        help="Fast static checks: no PKs, no managed flags, known field choices valid",
    )
    validate_parser.add_argument(
        "blueprint",
        type=Path,
        nargs="?",
        default=Path("common/authentik-blueprint/octopize-avatar-blueprint.yaml"),
        help="Blueprint file to validate (default: common/authentik-blueprint/octopize-avatar-blueprint.yaml)",
    )
    validate_parser.add_argument("--verbose", "-v", action="store_true")

    # ------------------------------------------------------------------
    # schema-check
    # ------------------------------------------------------------------
    schema_parser = subparsers.add_parser(
        "schema-check",
        help="Validate field choices against the Authentik source tree (no containers needed)",
    )
    schema_parser.add_argument(
        "--blueprint",
        type=Path,
        default=Path("common/authentik-blueprint/octopize-avatar-blueprint.yaml"),
        metavar="PATH",
        help="Blueprint to validate (default: common/authentik-blueprint/octopize-avatar-blueprint.yaml)",
    )
    schema_source = schema_parser.add_mutually_exclusive_group(required=True)
    schema_source.add_argument(
        "--authentik-version",
        metavar="VERSION",
        help="Authentik version to check against (e.g. 2026.2.1). "
             "Shallow-clones the repo; result cached in /tmp/authentik-VERSION.",
    )
    schema_source.add_argument(
        "--authentik-root",
        type=Path,
        metavar="PATH",
        help="Path to an already-cloned Authentik source tree.",
    )
    schema_parser.add_argument("--verbose", "-v", action="store_true")

    # ------------------------------------------------------------------
    # verify-live
    # ------------------------------------------------------------------
    verify_parser = subparsers.add_parser(
        "verify-live",
        help="Run the importer stepper inside a running Authentik worker (Docker or Kubernetes)",
    )
    verify_parser.add_argument(
        "--blueprint-name",
        default="octopize-avatar-sso-configuration",
        metavar="NAME",
        help="BlueprintInstance name to verify (default: octopize-avatar-sso-configuration)",
    )
    verify_mode = verify_parser.add_argument_group("target (Docker or Kubernetes)")
    verify_mode.add_argument(
        "--container",
        metavar="NAME",
        help="Docker container name. Auto-detected from running containers if omitted.",
    )
    verify_mode.add_argument(
        "--kubeconfig",
        metavar="PATH",
        help="Path to kubeconfig file. Switches to Kubernetes mode.",
    )
    verify_mode.add_argument(
        "--namespace",
        default="default",
        metavar="NS",
        help="Kubernetes namespace (default: default)",
    )
    verify_parser.add_argument("--verbose", "-v", action="store_true")

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "export":
        return _cmd_export(args)
    elif args.command == "validate":
        return _cmd_validate(args)
    elif args.command == "schema-check":
        return _cmd_schema_check(args)
    elif args.command == "verify-live":
        return _cmd_verify_live(args)


# ------------------------------------------------------------------
# Command handlers
# ------------------------------------------------------------------

def _cmd_export(args):
    from .converter import BlueprintConverter
    from .validator import BlueprintValidator

    if not args.input.exists():
        print(f"❌ Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    converter = BlueprintConverter(verbose=args.verbose)
    try:
        blueprint = converter.load_blueprint(args.input)
        converted = converter.convert_blueprint(blueprint)
        converter.save_blueprint(converted, args.output)
        print(f"\n✅ Conversion complete: {args.output}")
        print(f"   Processed {len(converted.get('entries', []))} entries")
    except Exception as e:
        print(f"❌ Conversion failed: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    if args.validate:
        if args.verbose:
            print(f"\n{'='*60}\nRunning validation…\n{'='*60}\n")
        if not BlueprintValidator().validate(args.output, verbose=args.verbose):
            sys.exit(1)


def _cmd_validate(args):
    from .validator import BlueprintValidator

    if not args.blueprint.exists():
        print(f"❌ Blueprint file not found: {args.blueprint}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"\n{'='*60}\nRunning validation…\n{'='*60}\n")

    if not BlueprintValidator().validate(args.blueprint, verbose=args.verbose):
        sys.exit(1)

    if args.verbose:
        print("\n✓ Blueprint validation passed")


def _cmd_schema_check(args):
    from .schema_checker import run

    if not args.blueprint.exists():
        print(f"❌ Blueprint file not found: {args.blueprint}", file=sys.stderr)
        sys.exit(1)

    ok = run(
        blueprint=args.blueprint,
        authentik_version=args.authentik_version,
        authentik_root=args.authentik_root,
        verbose=args.verbose,
    )
    if not ok:
        sys.exit(1)


def _cmd_verify_live(args):
    from .live_verifier import run

    exit_code = run(
        blueprint_name=args.blueprint_name,
        container=args.container,
        kubeconfig=args.kubeconfig,
        namespace=args.namespace,
        verbose=args.verbose,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
