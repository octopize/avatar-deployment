"""Live blueprint verification against a running Authentik worker.

Runs the entry-by-entry importer stepper inside a worker container
(Docker or Kubernetes) and exits non-zero if any entry fails.

This is the definitive check: it exercises the real Authentik serializers
against your actual configuration and catches errors that static analysis
cannot — FK reference failures, uniqueness violations, policy expression
errors, and anything else the importer would reject at runtime.
"""

import subprocess
import sys


# ---------------------------------------------------------------------------
# The stepper code executed inside the worker via `ak shell -c`
# ---------------------------------------------------------------------------

# Uses BLUEPRINT_NAME_PLACEHOLDER as a simple string replacement target to
# avoid brace-escaping conflicts with the f-strings inside the snippet itself.
_STEPPER_TEMPLATE = """\
from django.db import transaction
from authentik.blueprints.models import BlueprintInstance
from authentik.blueprints.v1.common import BlueprintEntryState
from authentik.blueprints.v1.importer import Importer
import sys

inst = BlueprintInstance.objects.get(name='BLUEPRINT_NAME_PLACEHOLDER')
importer = Importer.from_string(inst.retrieve(), inst.context)

failed = []
sid = transaction.savepoint()
try:
    for i, entry in enumerate(importer._import.entries):
        try:
            model_str = str(entry.model)
        except Exception:
            model_str = 'unknown'
        try:
            id_str = str(entry.id)
        except Exception:
            id_str = 'unknown'
        try:
            serializer = importer._validate_single(entry)
            if serializer:
                instance = serializer.save()
                entry._state = BlueprintEntryState(instance)
                print(f'  OK    [{i:>3}] {model_str} | {id_str}')
            else:
                print(f'  SKIP  [{i:>3}] {model_str} | {id_str}')
        except Exception as e:
            msg = str(e)[:200]
            print(f'  FAIL  [{i:>3}] {model_str} | {id_str}')
            print(f'         {type(e).__name__}: {msg}')
            failed.append((i, model_str, id_str, msg))
finally:
    transaction.savepoint_rollback(sid)

if failed:
    print(f'\\n{len(failed)} entry/entries FAILED:')
    for i, model, id_, msg in failed:
        print(f'  [{i}] {model} | {id_}: {msg}')
    sys.exit(1)
else:
    print(f'\\nAll entries OK.')
"""

# Log lines emitted by `ak shell` startup that we don't want in the output
_NOISE_PREFIXES = (
    "{",
    "Imported related",
    "Loaded ",
    "Starting ",
    "Finished ",
    "Booting ",
    "Enabled ",
    "MMDB",
    "Defaulted container",
)


def _filter_output(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped and not any(stripped.startswith(p) for p in _NOISE_PREFIXES):
            lines.append(line)
    return "\n".join(lines)


def _find_docker_worker() -> str | None:
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=authentik_worker", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    names = [n.strip() for n in result.stdout.splitlines() if n.strip()]
    return names[0] if names else None


def _run_command(cmd: list[str], blueprint_name: str) -> int:
    code = _STEPPER_TEMPLATE.replace("BLUEPRINT_NAME_PLACEHOLDER", blueprint_name)
    result = subprocess.run(cmd + ["ak", "shell", "-c", code], capture_output=True, text=True)
    output = _filter_output(result.stdout + result.stderr)
    print(output)
    # Exit code from ak shell -c propagates via returncode
    # But ak shell may return 0 even when sys.exit(1) is called inside,
    # so also check for FAIL lines in output as a safety net.
    if result.returncode != 0 or "  FAIL  [" in output:
        return 1
    return 0


def run_docker(container: str | None, blueprint_name: str, verbose: bool) -> int:
    """Run the stepper in a local Docker container. Returns exit code."""
    if container is None:
        container = _find_docker_worker()
        if container is None:
            print("❌ No running authentik_worker container found.", file=sys.stderr)
            print(
                "   Start the local environment first:\n"
                "   cd deployment-tool && bash run-noninteractive-local.sh",
                file=sys.stderr,
            )
            return 1
        print(f"→ Auto-detected worker: {container}")

    print(f"→ Running blueprint stepper in: {container}\n")
    return _run_command(["docker", "exec", container], blueprint_name)


def run_kubernetes(
    kubeconfig: str | None,
    namespace: str,
    blueprint_name: str,
    verbose: bool,
) -> int:
    """Run the stepper in a Kubernetes deployment. Returns exit code."""
    print(f"→ Running blueprint stepper in Kubernetes (namespace: {namespace})\n")
    cmd = ["kubectl"]
    if kubeconfig:
        cmd += ["--kubeconfig", kubeconfig]
    cmd += ["exec", "deployment/avatar-authentik-worker", "-n", namespace, "--"]
    return _run_command(cmd, blueprint_name)


def run(
    blueprint_name: str = "octopize-avatar-sso-configuration",
    container: str | None = None,
    kubeconfig: str | None = None,
    namespace: str = "default",
    verbose: bool = False,
) -> int:
    """
    Run live blueprint verification. Returns exit code (0 = pass, 1 = fail).

    Pass kubeconfig to target a Kubernetes cluster; omit for Docker mode.
    """
    print("=== Blueprint Live Verification ===")
    print(f"Blueprint: {blueprint_name}\n")

    if kubeconfig is not None:
        return run_kubernetes(kubeconfig, namespace, blueprint_name, verbose)
    else:
        return run_docker(container, blueprint_name, verbose)
