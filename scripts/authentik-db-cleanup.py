"""
authentik-db-cleanup — Django shell script.

Removes non-default authentik objects from a staging environment to prevent
configuration drift.  Must be executed inside the authentik worker container
via `ak shell`; do not run directly with Python.

Use the companion shell script instead:

    ./scripts/authentik-db-cleanup.sh [--live] [--kubeconfig PATH]

What it KEEPS:
  - Providers, Applications, Users, Groups, Sources  (never touched)
  - Authentik built-in defaults — flows/stages/policies/prompts whose
    names/slugs start with "default-", "initial-setup-", or "stage-default-"
  - System blueprint instances  (path prefix: system/, default/, migrations/)
  - System property/scope mappings  (managed field set by authentik)

What it DELETES (non-default only):
  - Flows, Stages (all subtypes), Policies (all subtypes), Prompts
  - Non-default brands
  - Non-system/non-default blueprint instances
  - User-created property/scope mappings (managed=None)

Safety: Provider.authorization_flow has on_delete=CASCADE, so before deleting
any flow the script nulls that FK on affected providers.  The blueprint
re-apply restores the correct reference.

The production blueprint (octopize-avatar-sso-configuration) re-applies
automatically after the worker restarts, recreating all Octopize objects.
"""

import os
from collections import defaultdict

# ---------------------------------------------------------------------------
# Configuration — set by the shell wrapper via DRY_RUN env var
# ---------------------------------------------------------------------------

DRY_RUN = os.environ.get("DRY_RUN", "true").lower() not in ("false", "0", "no")

DEFAULT_FLOW_SLUG_PREFIXES    = ("default-", "initial-setup")
DEFAULT_STAGE_NAME_PREFIXES   = ("default-", "initial-setup-", "stage-default-")
DEFAULT_POLICY_NAME_PREFIXES  = ("default-",)
DEFAULT_PROMPT_NAME_PREFIXES  = ("default-", "initial-setup-")

PROTECTED_BLUEPRINT_NAMES          = {"octopize-avatar-sso-configuration"}
PROTECTED_BLUEPRINT_NAME_PREFIXES  = ("Default -", "System -")
PROTECTED_BLUEPRINT_PATH_PREFIXES  = ("system/", "default/", "migrations/")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def matches_any(value: str, prefixes: tuple) -> bool:
    return any(value.startswith(p) for p in prefixes)

def section(title: str) -> None:
    print(f"\n{'=' * 62}\n  {title}\n{'=' * 62}")

def report(label: str, items: list) -> None:
    if not items:
        print(f"  {label}: (none)")
    else:
        print(f"  {label}: {len(items)} item(s)")
        for item in items:
            print(f"    - {item}")

def delete_qs(qs, label: str) -> int:
    count = qs.count()
    if not count:
        return 0
    if DRY_RUN:
        print(f"  [DRY RUN] Would delete {count} {label}")
    else:
        deleted, _ = qs.delete()
        print(f"  Deleted {deleted} {label}")
    return count

def update_qs(qs, label: str, **kwargs) -> None:
    count = qs.count()
    if not count:
        return
    if DRY_RUN:
        print(f"  [DRY RUN] Would update {count} {label}: {kwargs}")
    else:
        updated = qs.update(**kwargs)
        print(f"  Updated {updated} {label}: {kwargs}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_cleanup() -> None:
    from authentik.blueprints.models import BlueprintInstance
    from authentik.brands.models import Brand
    from authentik.core.models import PropertyMapping, Provider
    from authentik.flows.models import Flow, Stage
    from authentik.policies.models import Policy
    from authentik.stages.prompt.models import Prompt

    mode = "DRY RUN — no changes will be made" if DRY_RUN else "LIVE RUN — changes WILL be made"
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print(f"║  authentik-db-cleanup  [{mode}]")
    print("╚══════════════════════════════════════════════════════════════╝")

    total = 0

    # ------------------------------------------------------------------
    # 1. Flows
    # Provider.authorization_flow is CASCADE — null it before deleting.
    # ------------------------------------------------------------------
    section("1. Flows")
    all_flows   = list(Flow.objects.all())
    keep_flows  = [f for f in all_flows if     matches_any(f.slug, DEFAULT_FLOW_SLUG_PREFIXES)]
    drop_flows  = [f for f in all_flows if not matches_any(f.slug, DEFAULT_FLOW_SLUG_PREFIXES)]
    drop_pks    = [f.pk for f in drop_flows]

    report("Keeping (default)", [f.slug for f in keep_flows])
    report("Deleting",          [f"{f.slug}  [{f.designation}]" for f in drop_flows])

    affected = list(Provider.objects.filter(authorization_flow__in=drop_pks).values_list("name", flat=True))
    if affected:
        print(f"\n  ⚠  {len(affected)} provider(s) use a flow being deleted as authorization_flow")
        print("     (CASCADE would delete the provider — nulling the FK first):")
        for name in affected:
            print(f"       • {name!r}")
        update_qs(
            Provider.objects.filter(authorization_flow__in=drop_pks),
            "providers (authorization_flow → NULL)",
            authorization_flow=None,
        )

    total += delete_qs(
        Flow.objects.filter(pk__in=drop_pks),
        "flows (+ cascaded FlowStageBindings, PolicyBindings)",
    )

    # ------------------------------------------------------------------
    # 2. Stages
    # ------------------------------------------------------------------
    section("2. Stages")
    all_stages  = list(Stage.objects.all().select_subclasses())
    keep_stages = [s for s in all_stages if     matches_any(s.name, DEFAULT_STAGE_NAME_PREFIXES)]
    drop_stages = [s for s in all_stages if not matches_any(s.name, DEFAULT_STAGE_NAME_PREFIXES)]

    report("Keeping (default)", [f"{s.name}  [{type(s).__name__}]" for s in keep_stages])
    report("Deleting",          [f"{s.name}  [{type(s).__name__}]" for s in drop_stages])

    total += delete_qs(
        Stage.objects.filter(pk__in=[s.pk for s in drop_stages]),
        "stages (+ cascaded FlowStageBindings)",
    )

    # ------------------------------------------------------------------
    # 3. Policies
    # Must delete per concrete subclass to avoid Django MTI FK errors.
    # ------------------------------------------------------------------
    section("3. Policies")
    all_policies  = list(Policy.objects.all().select_subclasses())
    keep_policies = [p for p in all_policies if     matches_any(p.name, DEFAULT_POLICY_NAME_PREFIXES)]
    drop_policies = [p for p in all_policies if not matches_any(p.name, DEFAULT_POLICY_NAME_PREFIXES)]

    report("Keeping (default)", [f"{p.name}  [{type(p).__name__}]" for p in keep_policies])
    report("Deleting",          [f"{p.name}  [{type(p).__name__}]" for p in drop_policies])

    by_type: dict = defaultdict(list)
    for p in drop_policies:
        by_type[type(p)].append(p.pk)

    if DRY_RUN:
        print(f"  [DRY RUN] Would delete {len(drop_policies)} policies (+ cascaded PolicyBindings)")
        total += len(drop_policies)
    else:
        policy_total = 0
        for policy_type, pks in by_type.items():
            deleted, _ = policy_type.objects.filter(pk__in=pks).delete()
            policy_total += deleted
        print(f"  Deleted {policy_total} policy objects (+ cascaded PolicyBindings)")
        total += policy_total

    # ------------------------------------------------------------------
    # 4. Prompts
    # ------------------------------------------------------------------
    section("4. Prompts")
    all_prompts  = list(Prompt.objects.all())
    keep_prompts = [p for p in all_prompts if     matches_any(p.name, DEFAULT_PROMPT_NAME_PREFIXES)]
    drop_prompts = [p for p in all_prompts if not matches_any(p.name, DEFAULT_PROMPT_NAME_PREFIXES)]

    report("Keeping (default)", [p.name for p in keep_prompts])
    report("Deleting",          [p.name for p in drop_prompts])

    total += delete_qs(Prompt.objects.filter(pk__in=[p.pk for p in drop_prompts]), "prompts")

    # ------------------------------------------------------------------
    # 5. Brands — keep the default brand
    # ------------------------------------------------------------------
    section("5. Brands")
    all_brands  = list(Brand.objects.all())
    keep_brands = [b for b in all_brands if b.default or b.domain == "authentik-default"]
    drop_brands = [b for b in all_brands if not b.default and b.domain != "authentik-default"]

    report("Keeping", [f"domain={b.domain!r}  default={b.default}" for b in keep_brands])
    report("Deleting",[f"domain={b.domain!r}  default={b.default}" for b in drop_brands])

    total += delete_qs(Brand.objects.filter(pk__in=[b.pk for b in drop_brands]), "brands")

    # ------------------------------------------------------------------
    # 6. Blueprint instances — keep system/default/migrations/octopize
    # ------------------------------------------------------------------
    section("6. Blueprint Instances")

    def is_protected(bp: BlueprintInstance) -> bool:
        return (
            bp.name in PROTECTED_BLUEPRINT_NAMES
            or matches_any(bp.name, PROTECTED_BLUEPRINT_NAME_PREFIXES)
            or (bool(bp.path) and matches_any(bp.path, PROTECTED_BLUEPRINT_PATH_PREFIXES))
        )

    all_bps  = list(BlueprintInstance.objects.all())
    keep_bps = [b for b in all_bps if     is_protected(b)]
    drop_bps = [b for b in all_bps if not is_protected(b)]

    report("Keeping", [f"{b.name!r}  path={b.path!r}  status={b.status}" for b in keep_bps])
    report("Deleting",[f"{b.name!r}  path={b.path!r}  status={b.status}" for b in drop_bps])

    total += delete_qs(
        BlueprintInstance.objects.filter(pk__in=[b.pk for b in drop_bps]),
        "blueprint instances",
    )

    # ------------------------------------------------------------------
    # 7. Property/scope mappings — keep system-managed (managed field set)
    # ------------------------------------------------------------------
    section("7. Property / Scope Mappings")
    all_mappings  = list(PropertyMapping.objects.all().select_subclasses())
    keep_mappings = [m for m in all_mappings if m.managed]
    drop_mappings = [m for m in all_mappings if not m.managed]

    report("Keeping (system-managed)",      [f"{m.name!r}  managed={m.managed!r}" for m in keep_mappings])
    report("Deleting (user-created)",       [f"{m.name!r}  [{type(m).__name__}]"  for m in drop_mappings])

    total += delete_qs(
        PropertyMapping.objects.filter(pk__in=[m.pk for m in drop_mappings]),
        "property/scope mappings",
    )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    section("Summary")
    if DRY_RUN:
        print(f"  Objects that WOULD be deleted: {total}")
        print()
        print("  ⚠  DRY RUN — nothing was changed.  Pass --live to delete for real.")
    else:
        print(f"  Objects deleted: {total}")
        print()
        print("  ✓  Cleanup complete.")
        print()
        print("  Restart the worker to trigger blueprint re-apply:")
        print("    docker compose restart authentik_worker")
        print("    kubectl rollout restart deployment/avatar-authentik-worker")
    print()


run_cleanup()
