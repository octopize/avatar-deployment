#!/usr/bin/env python3
"""
Authentik Blueprint Converter: Primary Keys to !Find Commands

Converts Authentik blueprint exports from primary key (pk) references to
declarative !Find lookups, enabling portable and versionable blueprints.

Usage:
    python convert-blueprint-to-find.py input.yaml output.yaml [--validate]
    python convert-blueprint-to-find.py input.yaml output.yaml --validate --verbose

Note:
    The converter removes pk/managed fields and converts UUID references to !Find lookups.
    Some system-generated identifiers may contain UUIDs (e.g., outpost tokens) - these are
    expected and safe to keep as they're part of the identifier string, not FK references.
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml


# Custom YAML tag classes for Authentik
class FindTag(yaml.YAMLObject):
    """Represents a !Find lookup in the blueprint."""
    yaml_tag = "!Find"
    yaml_loader = yaml.SafeLoader

    def __init__(self, model, identifiers):
        self.model = model
        self.identifiers = identifiers

    def __eq__(self, other):
        if not isinstance(other, FindTag):
            return False
        return self.model == other.model and self.identifiers == other.identifiers

    def __repr__(self):
        return f"FindTag({self.model!r}, {self.identifiers!r})"

    @classmethod
    def from_yaml(cls, loader, node):
        values = loader.construct_sequence(node)
        return cls(values[0], values[1] if len(values) > 1 else [])

    @classmethod
    def to_yaml(cls, dumper, data):
        return dumper.represent_sequence(
            cls.yaml_tag,
            [data.model, data.identifiers],
            flow_style=True
        )


class ContextTag(yaml.YAMLObject):
    """Represents a !Context reference in the blueprint."""
    yaml_tag = "!Context"
    yaml_loader = yaml.SafeLoader

    def __init__(self, name, default=None):
        self.name = name
        self.default = default

    def __eq__(self, other):
        if not isinstance(other, ContextTag):
            return False
        return self.name == other.name and self.default == other.default

    def __repr__(self):
        return f"ContextTag({self.name!r}, {self.default!r})"

    @classmethod
    def from_yaml(cls, loader, node):
        # Handle both scalar (reference without default) and sequence (with default)
        if isinstance(node, yaml.ScalarNode):
            name = loader.construct_scalar(node)
            return cls(name, None)
        else:
            values = loader.construct_sequence(node)
            return cls(values[0], values[1] if len(values) > 1 else None)

    @classmethod
    def to_yaml(cls, dumper, data):
        # If no default, use scalar notation: !Context key
        # If default exists, use sequence notation: !Context [key, default]
        if data.default is None:
            return dumper.represent_scalar(cls.yaml_tag, data.name)
        else:
            values = [data.name, data.default]
            return dumper.represent_sequence(cls.yaml_tag, values, flow_style=True)


class FormatTag(yaml.YAMLObject):
    """Represents a !Format reference in the blueprint."""
    yaml_tag = "!Format"
    yaml_loader = yaml.SafeLoader

    def __init__(self, template, args):
        self.template = template
        self.args = args

    def __eq__(self, other):
        if not isinstance(other, FormatTag):
            return False
        return self.template == other.template and self.args == other.args

    def __repr__(self):
        return f"FormatTag({self.template!r}, {self.args!r})"

    @classmethod
    def from_yaml(cls, loader, node):
        values = loader.construct_sequence(node)
        return cls(values[0], values[1:])

    @classmethod
    def to_yaml(cls, dumper, data):
        # Format: !Format [template, arg1, arg2, ...]
        values = [data.template] + data.args
        return dumper.represent_sequence(cls.yaml_tag, values, flow_style=True)


class KeyOfTag(yaml.YAMLObject):
    """Represents a !KeyOf reference in the blueprint.

    !KeyOf references objects defined earlier in the same blueprint by their id field.
    This is more reliable than !Find for objects created within the same blueprint,
    as it resolves during apply time using the entry's created instance.
    """
    yaml_tag = "!KeyOf"
    yaml_loader = yaml.SafeLoader

    def __init__(self, id_ref):
        self.id_ref = id_ref

    def __eq__(self, other):
        if not isinstance(other, KeyOfTag):
            return False
        return self.id_ref == other.id_ref

    def __repr__(self):
        return f"KeyOfTag({self.id_ref!r})"

    @classmethod
    def from_yaml(cls, loader, node):
        return cls(loader.construct_scalar(node))

    @classmethod
    def to_yaml(cls, dumper, data):
        return dumper.represent_scalar(cls.yaml_tag, data.id_ref)


class EnvTag(yaml.YAMLObject):
    """Represents an !Env lookup in the blueprint.

    !Env resolves to the value of the given environment variable at blueprint
    apply time. Can optionally include a default value.
    Syntax: !Env my_env_var  OR  !Env [my_env_var, default_value]
    """
    yaml_tag = "!Env"
    yaml_loader = yaml.SafeLoader

    def __init__(self, var_name, default=None):
        self.var_name = var_name
        self.default = default

    def __eq__(self, other):
        if not isinstance(other, EnvTag):
            return False
        return self.var_name == other.var_name and self.default == other.default

    def __repr__(self):
        return f"EnvTag({self.var_name!r}, {self.default!r})"

    @classmethod
    def from_yaml(cls, loader, node):
        if isinstance(node, yaml.ScalarNode):
            var_name = loader.construct_scalar(node)
            return cls(var_name, None)
        else:
            values = loader.construct_sequence(node)
            return cls(values[0], values[1] if len(values) > 1 else None)

    @classmethod
    def to_yaml(cls, dumper, data):
        if data.default is None:
            return dumper.represent_scalar(cls.yaml_tag, data.var_name)
        else:
            values = [data.var_name, data.default]
            return dumper.represent_sequence(cls.yaml_tag, values, flow_style=True)


# Custom Dumper that uses literal block style (|) for multi-line strings.
# This is critical for preserving newlines in Python expressions (e.g. ExpressionPolicy).
# Without this, yaml.Dumper uses quoted scalars which fold newlines into spaces.
class LiteralBlockDumper(yaml.Dumper):
    pass


def _literal_str_representer(dumper, data):
    """Use literal block style (|) for strings containing newlines."""
    if "\n" in data:
        # Strip trailing whitespace from each line to keep YAML clean
        cleaned = "\n".join(line.rstrip() for line in data.split("\n"))
        return dumper.represent_scalar("tag:yaml.org,2002:str", cleaned, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


LiteralBlockDumper.add_representer(str, _literal_str_representer)

# Register the custom tags with PyYAML (on both default Dumper and our custom one)
for dumper_cls in (yaml.Dumper, LiteralBlockDumper):
    dumper_cls.add_representer(FindTag, FindTag.to_yaml)
    dumper_cls.add_representer(ContextTag, ContextTag.to_yaml)
    dumper_cls.add_representer(FormatTag, FormatTag.to_yaml)
    dumper_cls.add_representer(KeyOfTag, KeyOfTag.to_yaml)
    dumper_cls.add_representer(EnvTag, EnvTag.to_yaml)


class BlueprintConverter:
    """Converts Authentik blueprints from PK references to !Find lookups."""

    # Entry grouping configuration: defines section order and organization
    # Format: (section_name, model_patterns, requires_sub_grouping)
    # ORDER IS CRITICAL: Dependencies must come before dependents
    # 1. Groups (no dependencies)
    # 2. Flows (no dependencies)
    # 3. Prompts (no dependencies)
    # 4. Policies (no dependencies)
    # 5. Stages (reference prompts, policies, flows)
    # 6. Flow Stage Bindings (reference flows, stages)
    # 7. Policy Bindings (reference policies, flow stage bindings)
    # 8. Scope Mappings (no dependencies)
    # 9. OAuth Provider (references flows, scope mappings)
    # 10. Application (references provider)
    # 11. Brand (references application, flows)
    ENTRY_GROUPS = [
        ("GROUPS", ["authentik_core.group"], False),
        ("FLOWS", ["authentik_flows.flow"], False),
        ("PROMPTS", ["authentik_stages_prompt.prompt"], False),
        ("POLICIES", [
            "authentik_policies_expression.expressionpolicy",
            "authentik_policies_password.passwordpolicy",
            "authentik_policies_event_matcher.eventmatcherpolicy",
        ], False),
        ("STAGES", [
            "authentik_stages_email.emailstage",
            "authentik_stages_identification.identificationstage",
            "authentik_stages_password.passwordstage",
            "authentik_stages_prompt.promptstage",
            "authentik_stages_user_write.userwritestage",
            "authentik_stages_user_login.userloginstage",
            "authentik_stages_user_logout.userlogoutstage",
            "authentik_stages_consent.consentstage",
            "authentik_stages_dummy.dummystage",
        ], False),
        ("FLOW STAGE BINDINGS", ["authentik_flows.flowstagebinding"], True),
        ("POLICY BINDINGS", ["authentik_policies.policybinding"], False),
        ("SCOPE MAPPINGS", ["authentik_providers_oauth2.scopemapping"], False),
        ("OAUTH PROVIDER", ["authentik_providers_oauth2.oauth2provider"], False),
        ("APPLICATION", ["authentik_core.application"], False),
        ("BRAND", ["authentik_brands.brand"], False),
    ]

    # Model-specific identifier fields (used for !Find lookups)
    IDENTIFIER_FIELDS = {
        "authentik_core.group": ["name"],
        "authentik_core.user": ["username"],
        "authentik_flows.flow": ["slug"],
        "authentik_stages_email.emailstage": ["name"],
        "authentik_stages_identification.identificationstage": ["name"],
        "authentik_stages_password.passwordstage": ["name"],
        "authentik_stages_prompt.prompt": ["field_key", "name"],
        "authentik_stages_prompt.promptstage": ["name"],
        "authentik_stages_user_write.userwritestage": ["name"],
        "authentik_stages_user_login.userloginstage": ["name"],
        "authentik_stages_user_logout.userlogoutstage": ["name"],
        "authentik_stages_consent.consentstage": ["name"],
        "authentik_stages_dummy.dummystage": ["name"],
        "authentik_policies_expression.expressionpolicy": ["name"],
        "authentik_policies_password.passwordpolicy": ["name"],
        "authentik_policies_event_matcher.eventmatcherpolicy": ["name"],
        "authentik_policies.policybinding": ["target", "policy", "order"],
        "authentik_flows.flowstagebinding": ["target", "stage", "order"],
        "authentik_providers_oauth2.oauth2provider": ["name"],
        "authentik_providers_oauth2.scopemapping": ["name"],
        "authentik_core.application": ["slug"],
        "authentik_brands.brand": ["domain"],
        "authentik_crypto.certificatekeypair": ["name"],
        "authentik_outposts.outpost": ["name"],
        "authentik_events.notificationtransport": ["name"],
        "authentik_events.notificationrule": ["name"],
        "authentik_providers_proxy.proxyprovider": ["name"],
        "authentik_providers_saml.samlprovider": ["name"],
        "authentik_providers_ldap.ldapprovider": ["name"],
        "authentik_providers_radius.radiusprovider": ["name"],
        "authentik_providers_scim.scimprovider": ["name"],
        "authentik_tenants.tenant": ["domain"],
        "authentik_blueprints.metaapplyblueprint": ["name"],
        "authentik_rbac.role": ["name"],
    }

    # Models where 'managed' field should be preferred for !Find lookups
    # when available (non-null). This prevents identifier collisions when
    # custom objects share field values with built-in managed objects.
    # Example: GrabLicense (custom, scope_name=profile) vs default OpenID 'profile'
    # (managed, scope_name=profile) — both have scope_name=profile but must be
    # distinguished in !Find lookups.
    MANAGED_IDENTIFIER_MODELS = {
        "authentik_providers_oauth2.scopemapping",
    }

    # Fields that should never be in the output
    FORBIDDEN_FIELDS = {"pk", "managed"}

    # UUID pattern for detection
    UUID_PATTERN = re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    )

    # Default Authentik object name prefixes - these exist in DB and should use !Find
    DEFAULT_OBJECT_PREFIXES = (
        "default-",
        "authentik-",
        "authentik default",
    )

    # Stages with these prefixes come from OPTIONAL authentik example blueprints
    # (e.g. blueprints/example/flows-recovery-email-verification.yaml) that have
    # label `instantiate: "false"` — they are NOT auto-loaded and NOT guaranteed
    # to exist in every deployment.  We must include them as blueprint entries
    # and reference them via !KeyOf, not !Find.
    REQUIRED_DEFAULT_STAGE_PREFIXES = (
        "default-recovery-",
    )

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        # Maps pk -> entry data for lookups
        self.pk_to_entry: Dict[str, Dict] = {}
        # Tracks all models and their identifiers
        self.model_entries: Dict[str, List[Dict]] = {}
        # Track PKs of entries that should be kept (custom flows + their dependencies)
        self.required_pks: Set[str] = set()
        # Track PKs of custom entries (defined in this blueprint, not default Authentik objects)
        # These will use !KeyOf references
        self.custom_entry_pks: Set[str] = set()
        # Maps pk -> generated id (for !KeyOf references)
        self.pk_to_id: Dict[str, str] = {}

    def log(self, message: str):
        """Print verbose logging."""
        if self.verbose:
            print(f"[INFO] {message}", file=sys.stderr)

    def is_default_object(self, entry: Dict) -> bool:
        """Check if an entry represents a default Authentik object.

        Default objects already exist in Authentik's database and should be
        referenced via !Find. Custom objects are created by this blueprint
        and should be referenced via !KeyOf.
        """
        attrs = entry.get("attrs", {})
        name = attrs.get("name", "")
        slug = attrs.get("slug", "")

        # Check name/slug for default prefixes
        for prefix in self.DEFAULT_OBJECT_PREFIXES:
            if name.lower().startswith(prefix) or slug.lower().startswith(prefix):
                # Some "default-*" stages are from optional (non-auto-loaded)
                # blueprints and must be treated as custom objects.
                if any(
                    name.lower().startswith(p) or slug.lower().startswith(p)
                    for p in self.REQUIRED_DEFAULT_STAGE_PREFIXES
                ):
                    return False
                return True

        # Specific default objects by name
        default_names = {
            "initial-setup",
            "Change your password",
            "stage-default-oobe-password",
        }
        if name in default_names or slug in default_names:
            return True

        return False

    def _resolve_pk_to_name(self, pk: str) -> Optional[str]:
        """Resolve a PK to a human-readable name (slug or name) from the index."""
        entry = self.pk_to_entry.get(str(pk))
        if not entry:
            return None
        attrs = entry.get("attrs", {})
        # Prefer slug, then name, then field_key
        for field in ("slug", "name", "field_key"):
            value = attrs.get(field)
            if value and isinstance(value, str):
                return value.lower().replace(" ", "-")
        return None

    def generate_entry_id(self, entry: Dict) -> str:
        """Generate a unique id for an entry based on its model and identifiers.

        The id is used for !KeyOf references within the blueprint.

        For most models: uses slug or name directly.
        For binding models (flowstagebinding, policybinding): generates a
        composite descriptive id from the referenced objects, e.g.
        ``flow-slug-bind-stage-name-order-10``.
        """
        model = entry.get("model", "")
        attrs = entry.get("attrs", {})

        # Special handling for binding models: build composite descriptive ids
        if model == "authentik_flows.flowstagebinding":
            target_name = self._resolve_pk_to_name(attrs.get("target", "")) or "unknown-flow"
            stage_name = self._resolve_pk_to_name(attrs.get("stage", "")) or "unknown-stage"
            order = attrs.get("order", 0)
            return f"{target_name}-bind-{stage_name}-order-{order}"

        if model == "authentik_policies.policybinding":
            target_pk = attrs.get("target", "")
            target_name = self._resolve_pk_to_name(target_pk) or "unknown-target"
            # Target might be a flowstagebinding (which has no name/slug);
            # in that case, use the id we already generated for it
            if target_name == "unknown-target" and str(target_pk) in self.pk_to_id:
                target_name = self.pk_to_id[str(target_pk)]
            policy_name = self._resolve_pk_to_name(attrs.get("policy", "")) or "unknown-policy"
            order = attrs.get("order", 0)
            return f"{policy_name}-bind-{target_name}-order-{order}"

        # Standard models: use identifier fields (slug, name, etc.)
        id_fields = self.IDENTIFIER_FIELDS.get(model, ["name"])

        for field in id_fields:
            if field in attrs:
                value = attrs[field]
                if isinstance(value, str) and not self.UUID_PATTERN.match(value):
                    return value.lower().replace(" ", "-")

        # Fallback: use model + first 8 chars of pk (should rarely happen)
        pk = entry.get("identifiers", {}).get("pk", "unknown")
        return f"{model.split('.')[-1]}-{pk[:8]}"

    def load_blueprint(self, path: Path) -> Dict:
        """Load YAML blueprint file."""
        self.log(f"Loading blueprint from {path}")
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def save_blueprint(self, blueprint: Dict, path: Path):
        """Save YAML blueprint file with custom YAML tags and organized sections.

        Converts [[PLACEHOLDER]] markers to !Env tags so that authentik resolves
        values from environment variables at blueprint apply time.

        Args:
            blueprint: Blueprint data structure
            path: Output file path
        """
        self.log(f"Saving converted blueprint to {path}")

        # Convert marker dicts to tag objects
        blueprint_with_tags = self._convert_markers_to_tags(blueprint)

        # Convert [[PLACEHOLDER]] to !Env tags
        blueprint_with_tags = self._convert_to_env_placeholders(blueprint_with_tags)

        # Remove empty context if it exists at top level
        if "context" in blueprint_with_tags and not blueprint_with_tags["context"]:
            del blueprint_with_tags["context"]

        with open(path, "w") as f:
            header = """\
# yaml-language-server: $schema=https://goauthentik.io/blueprints/schema.json
---
# Octopize Avatar - Authentik Blueprint
# This blueprint configures SSO authentication for the Avatar API platform
# including custom flows, stages, policies, and email templates
#
# All deployment-specific values are resolved at apply time via !Env tags.
# The following environment variables must be set in the authentik deployment:
#   AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN                - Base domain (e.g., avatar.yourcompany.com)
#   AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_ID             - OAuth2 Client ID
#   AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_SECRET         - OAuth2 Client Secret
#   AVATAR_AUTHENTIK_BLUEPRINT_API_REDIRECT_URI      - Full redirect URI for API
#   AVATAR_AUTHENTIK_BLUEPRINT_SELF_SERVICE_LICENSE   - License type for self-service signups

"""
            f.write(header)

            # Write top-level metadata (version, context)
            top_level = {}
            if "version" in blueprint_with_tags:
                top_level["version"] = blueprint_with_tags["version"]
            if "context" in blueprint_with_tags:
                top_level["context"] = blueprint_with_tags["context"]
            if "metadata" in blueprint_with_tags:
                top_level["metadata"] = blueprint_with_tags["metadata"]

            # Write top-level keys first
            if top_level:
                yaml.dump(
                    top_level,
                    f,
                    default_flow_style=False,
                    sort_keys=True,
                    allow_unicode=True,
                    width=999999,
                    Dumper=LiteralBlockDumper,
                )

            # Group entries by section
            entries = blueprint_with_tags.get("entries", [])
            grouped_sections = self._group_entries_by_section(entries)

            # Write entries section header
            f.write("entries:\n")

            # Write each section with headers
            for section_name, section_entries, requires_sub_grouping in grouped_sections:
                # Write main section header
                f.write(self._create_section_header(section_name))

                if requires_sub_grouping:
                    # Get sub-groups for this section
                    sub_groups = self._sub_group_entries(section_name, section_entries)
                    for sub_group_name, sub_group_entries in sub_groups:
                        # Write sub-section header
                        f.write(self._create_section_header(sub_group_name, sub_header=True))

                        # Write entries for this sub-group
                        for entry in sub_group_entries:
                            entry_yaml = yaml.dump(
                                [entry],
                                default_flow_style=False,
                                sort_keys=True,
                                allow_unicode=True,
                                width=999999,
                                Dumper=LiteralBlockDumper,
                            )
                            # Remove the leading "- " from first line and indent rest
                            # Preserve empty lines (needed for literal block scalars)
                            lines = entry_yaml.rstrip("\n").split("\n")
                            if lines:
                                f.write(f"  - {lines[0][2:]}\n")  # First line: "  - " + content
                                for line in lines[1:]:
                                    if line:  # Indent non-empty lines
                                        f.write(f"  {line}\n")
                                    else:  # Preserve empty lines (literal blocks)
                                        f.write("\n")
                else:
                    # Write entries normally (no sub-grouping)
                    for entry in section_entries:
                        entry_yaml = yaml.dump(
                            [entry],
                            default_flow_style=False,
                            sort_keys=True,
                            allow_unicode=True,
                            width=999999,
                            Dumper=LiteralBlockDumper,
                        )
                        # Remove the leading "- " from first line and indent rest
                        # Preserve empty lines (needed for literal block scalars)
                        lines = entry_yaml.rstrip("\n").split("\n")
                        if lines:
                            f.write(f"  - {lines[0][2:]}\n")  # First line: "  - " + content
                            for line in lines[1:]:
                                if line:  # Indent non-empty lines
                                    f.write(f"  {line}\n")
                                else:  # Preserve empty lines (literal blocks)
                                    f.write("\n")

    def _convert_markers_to_tags(self, obj):
        """Convert __FIND__, __KEYOF__, __CONTEXT__, __FORMAT__, and __ENV__ marker dicts to tag objects."""
        if isinstance(obj, dict):
            if "__FIND__" in obj and len(obj) == 1:
                data = obj["__FIND__"]
                if isinstance(data, list) and len(data) >= 2:
                    # Recursively convert nested markers in the identifiers list
                    converted_identifiers = self._convert_markers_to_tags(data[1])
                    return FindTag(data[0], converted_identifiers)
            if "__KEYOF__" in obj and len(obj) == 1:
                id_ref = obj["__KEYOF__"]
                return KeyOfTag(id_ref)
            if "__CONTEXT__" in obj and len(obj) == 1:
                data = obj["__CONTEXT__"]
                # Handle both string format (reference without default) and list format (with default)
                if isinstance(data, str):
                    return ContextTag(data, None)
                elif isinstance(data, list) and len(data) >= 1:
                    name = data[0]
                    default = data[1] if len(data) > 1 else None
                    return ContextTag(name, default)
            if "__FORMAT__" in obj and len(obj) == 1:
                data = obj["__FORMAT__"]
                if isinstance(data, list) and len(data) >= 1:
                    template = data[0]
                    # Recursively convert nested markers in the args
                    converted_args = [self._convert_markers_to_tags(arg) for arg in data[1:]]
                    return FormatTag(template, converted_args)
            if "__ENV__" in obj and len(obj) == 1:
                data = obj["__ENV__"]
                if isinstance(data, str):
                    return EnvTag(data, None)
                elif isinstance(data, list) and len(data) >= 1:
                    var_name = data[0]
                    default = data[1] if len(data) > 1 else None
                    return EnvTag(var_name, default)
            return {k: self._convert_markers_to_tags(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_markers_to_tags(item) for item in obj]
        return obj

    def build_pk_index(self, blueprint: Dict):
        """Build index of all entries by their primary key.

        Also identifies custom entries (those that will be created by this blueprint)
        and generates IDs for !KeyOf references.

        Uses two passes:
        1. Index all entries by PK so cross-references can be resolved.
        2. Generate descriptive IDs for custom entries (bindings need pass 1 complete).
        """
        self.log("Building primary key index")

        # Pass 1: Index ALL entries by PK
        custom_entries: list[tuple[str, Dict]] = []
        for entry in blueprint.get("entries", []):
            identifiers = entry.get("identifiers", {})
            model = entry.get("model")
            attrs = entry.get("attrs", {})

            if "pk" in identifiers:
                pk = str(identifiers["pk"])
                self.pk_to_entry[pk] = {
                    "model": model,
                    "identifiers": identifiers,
                    "attrs": attrs,
                }
                self.log(f"  Indexed {model} with pk={pk}")

                # Check if this is a custom entry (will be defined in the blueprint)
                name = attrs.get("name", "")
                slug = attrs.get("slug", "")

                is_custom = (
                    name.startswith("avatar-") or
                    slug.startswith("avatar-") or
                    name.startswith("Octopize") or
                    (not self.is_default_object(entry) and not self.should_skip_entry(entry))
                )

                if is_custom:
                    self.custom_entry_pks.add(pk)
                    custom_entries.append((pk, entry))

            # Also index by model type
            if model not in self.model_entries:
                self.model_entries[model] = []
            self.model_entries[model].append(entry)

        # Pass 2: Generate IDs for custom entries (all PKs now indexed)
        for pk, entry in custom_entries:
            entry_id = self.generate_entry_id(entry)
            self.pk_to_id[pk] = entry_id
            self.log(f"    Custom entry {pk}, generated id: {entry_id}")

    def collect_dependencies(self, pk: str, depth: int = 0) -> None:
        """Recursively collect all dependencies of an entry by PK."""
        if pk in self.required_pks:
            return  # Already processed

        entry = self.pk_to_entry.get(str(pk))
        if not entry:
            return

        indent = "  " * depth
        model = entry.get("model", "unknown")
        attrs = entry.get("attrs", {})
        name = attrs.get("name", attrs.get("slug", "unknown"))

        self.log(f"{indent}Adding dependency: {model} ({name})")
        self.required_pks.add(str(pk))

        # Recursively find UUID references in attrs
        self._collect_uuid_dependencies(attrs, depth + 1)

    def _collect_uuid_dependencies(self, obj, depth: int = 0):
        """Recursively scan for UUID references and add them as dependencies."""
        if isinstance(obj, str) and self.UUID_PATTERN.match(obj):
            # This is a UUID that might be a PK reference
            if obj in self.pk_to_entry:
                self.collect_dependencies(obj, depth)
        elif isinstance(obj, list):
            for item in obj:
                self._collect_uuid_dependencies(item, depth)
        elif isinstance(obj, dict):
            for value in obj.values():
                self._collect_uuid_dependencies(value, depth)

    def identify_custom_flows_and_dependencies(self, blueprint: Dict):
        """Identify custom Avatar flows and collect all their dependencies."""
        self.log("Identifying custom flows and their dependencies...")

        avatar_custom_flows = [
            "avatar-authentication-flow",
            "avatar-self-service-signup-flow",
            "avatar-recovery-flow"
        ]

        # First pass: find custom flows
        custom_flow_pks = []
        for entry in blueprint.get("entries", []):
            model = entry.get("model", "")
            if model == "authentik_flows.flow":
                slug = entry.get("attrs", {}).get("slug", "")
                if slug in avatar_custom_flows:
                    pk = entry.get("identifiers", {}).get("pk")
                    if pk:
                        custom_flow_pks.append(str(pk))
                        self.log(f"Found custom flow: {slug} (PK: {pk})")

        # Collect dependencies for each custom flow
        for pk in custom_flow_pks:
            self.log(f"\nCollecting dependencies for flow PK {pk}:")
            self.collect_dependencies(pk)

        # Also collect flow stage bindings for these flows
        self.log("\nCollecting flow stage bindings for custom flows...")
        for entry in blueprint.get("entries", []):
            model = entry.get("model", "")
            if model == "authentik_flows.flowstagebinding":
                target_pk = entry.get("attrs", {}).get("target")
                if target_pk and str(target_pk) in custom_flow_pks:
                    # This binding belongs to a custom flow - keep it and its stage
                    binding_pk = entry.get("identifiers", {}).get("pk")
                    stage_pk = entry.get("attrs", {}).get("stage")
                    if binding_pk:
                        self.collect_dependencies(str(binding_pk))
                    if stage_pk:
                        self.collect_dependencies(str(stage_pk))

        self.log(f"\nTotal required entries: {len(self.required_pks)}")


    def get_identifier_for_pk(self, pk: str, expected_model: Optional[str] = None) -> Optional[Dict]:
        """Resolve a PK to its identifier fields for !Find lookup."""
        entry = self.pk_to_entry.get(str(pk))
        if not entry:
            self.log(f"  WARNING: Could not resolve PK {pk}")
            return None

        model = entry["model"]
        if expected_model and model != expected_model:
            self.log(f"  WARNING: PK {pk} is {model}, expected {expected_model}")

        # Get identifier fields for this model
        id_fields = self.IDENTIFIER_FIELDS.get(model, ["name"])

        # Build identifier dict from attrs
        attrs = entry["attrs"]
        identifiers = {}

        # For certain models, prefer 'managed' field when available (non-null)
        # This prevents collisions with custom objects that share the same
        # identifier values (e.g. GrabLicense and default profile both have
        # scope_name=profile, but managed uniquely identifies the default one)
        if model in self.MANAGED_IDENTIFIER_MODELS:
            managed_value = attrs.get("managed")
            if managed_value is not None:
                identifiers["managed"] = managed_value
                id_list = ["managed", managed_value]
                self.log(f"  Using managed identifier for {model}: {managed_value}")
                return {"model": model, "identifiers": id_list}

        for field in id_fields:
            if field in attrs:
                value = attrs[field]
                # Recursively convert UUID references in identifier values
                identifiers[field] = self.convert_value(value, f"identifier.{field}")
            elif field in entry["identifiers"]:
                value = entry["identifiers"][field]
                identifiers[field] = self.convert_value(value, f"identifier.{field}")

        if not identifiers:
            self.log(f"  WARNING: No identifiers found for {model} pk={pk}")
            return None

        # Convert dict to flat list for !Find format: [key1, value1, key2, value2, ...]
        id_list = []
        for k, v in identifiers.items():
            id_list.extend([k, v])

        return {"model": model, "identifiers": id_list}

    def convert_value(self, value, field_path: str = "") -> Any:
        """Convert a value, replacing PK references with !KeyOf or !Find lookups.

        Uses !KeyOf for custom entries (defined in this blueprint) and !Find for
        default Authentik objects (already exist in the database).
        """
        # Fields that should never be converted (they are always simple values)
        NEVER_CONVERT_FIELDS = {
            "order", "port", "timeout", "amount_digits", "amount_lowercase",
            "amount_symbols", "amount_uppercase", "length_min", "hibp_allowed_count",
            "zxcvbn_score_threshold", "token_expiry", "recovery_max_attempts",
            "failed_attempts_before_cancel"
        }

        # Extract field name from path (e.g., "attrs.order" -> "order")
        field_name = field_path.split(".")[-1] if "." in field_path else field_path

        # Handle UUID strings (potential FK references)
        if isinstance(value, str) and self.UUID_PATTERN.match(value):
            pk = str(value)

            # Check if this is a custom entry (use !KeyOf) or default (use !Find)
            if pk in self.custom_entry_pks and pk in self.pk_to_id:
                entry_id = self.pk_to_id[pk]
                self.log(f"  Converted PK {pk} -> !KeyOf {entry_id}")
                return {"__KEYOF__": entry_id}

            # Try to resolve as PK for !Find lookup
            lookup = self.get_identifier_for_pk(value)
            if lookup:
                model = lookup["model"]
                identifiers = lookup["identifiers"]  # This is now a flat list

                self.log(f"  Converted PK {value} -> !Find [{model}, {identifiers}]")
                return {"__FIND__": [model, identifiers]}
            else:
                self.log(f"  WARNING: Unresolved UUID at {field_path}: {value}")

        # Handle integer PKs (common in older exports or certain relationships)
        # BUT: skip fields that are known to be simple integers (like order, port, etc.)
        elif isinstance(value, int) and field_name not in NEVER_CONVERT_FIELDS:
            pk = str(value)

            # Check if this is a custom entry (use !KeyOf) or default (use !Find)
            if pk in self.custom_entry_pks and pk in self.pk_to_id:
                entry_id = self.pk_to_id[pk]
                self.log(f"  Converted integer PK {pk} -> !KeyOf {entry_id}")
                return {"__KEYOF__": entry_id}

            # Try to resolve as PK
            lookup = self.get_identifier_for_pk(str(value))
            if lookup:
                model = lookup["model"]
                identifiers = lookup["identifiers"]  # This is now a flat list

                self.log(f"  Converted integer PK {value} -> !Find [{model}, {identifiers}]")
                return {"__FIND__": [model, identifiers]}
            # If not a known PK, keep as integer
            return value

        # Handle lists
        elif isinstance(value, list):
            return [self.convert_value(item, f"{field_path}[]") for item in value]

        # Handle dicts
        elif isinstance(value, dict):
            return {k: self.convert_value(v, f"{field_path}.{k}") for k, v in value.items()}

        return value

    def transform_group_attrs(self, attrs: Dict) -> Dict:
        """Transform group attributes - replace hardcoded license with context."""
        if "attributes" in attrs and isinstance(attrs["attributes"], dict):
            if "license" in attrs["attributes"]:
                # Replace hardcoded license value with context reference
                attrs["attributes"]["license"] = {"__CONTEXT__": "license_type"}

        # Remove users field (shouldn't be in templates)
        if "users" in attrs:
            del attrs["users"]

        return attrs

    def transform_application_attrs(self, attrs: Dict) -> Dict:
        """Transform application attributes - use context and Format for dynamic values."""
        # Replace hardcoded meta_launch_url with Format using domain context
        if "meta_launch_url" in attrs:
            attrs["meta_launch_url"] = {
                "__FORMAT__": ["https://%s/web", {"__CONTEXT__": "domain"}]
            }

        # Replace hardcoded name with context
        if "name" in attrs and attrs["name"] in ["avatar-api", "Avatar API"]:
            attrs["name"] = {"__CONTEXT__": "app_name"}

        # Provider will be handled by convert_value (UUID/int -> !Find)
        # but we need to ensure it references the right provider

        return attrs

    def transform_oauth_provider_attrs(self, attrs: Dict) -> Dict:
        """Transform OAuth provider attributes - replace secrets and URLs with placeholders."""
        # Replace hardcoded client_id
        if "client_id" in attrs:
            attrs["client_id"] = "[[CLIENT_ID]]"

        # Replace hardcoded client_secret
        if "client_secret" in attrs:
            attrs["client_secret"] = "[[CLIENT_SECRET]]"

        # Replace provider name with Format using context
        if "name" in attrs and ("Provider for" in attrs["name"] or attrs["name"] in ["Provider for avatar-api", "Provider for Avatar API"]):
            attrs["name"] = {
                "__FORMAT__": ["Provider for %s", {"__CONTEXT__": "app_name"}]
            }

        # Replace redirect URIs with template placeholders
        if "redirect_uris" in attrs and isinstance(attrs["redirect_uris"], list):
            for uri_entry in attrs["redirect_uris"]:
                if isinstance(uri_entry, dict) and "url" in uri_entry:
                    # Replace hardcoded redirect URI with placeholder
                    uri_entry["url"] = "[[API_REDIRECT_URI]]"

        return attrs

    def transform_expression_policy_attrs(self, attrs: Dict) -> Dict:
        """Transform expression policy attributes - replace hardcoded values with placeholders."""
        if "expression" in attrs and isinstance(attrs["expression"], str):
            # Replace hardcoded "demo" license with template placeholder
            attrs["expression"] = attrs["expression"].replace(
                'group.attributes["license"] = "demo"',
                'group.attributes["license"] = "[[SELF_SERVICE_LICENSE]]"'
            )

        return attrs

    def transform_brand_attrs(self, attrs: Dict) -> Dict:
        """Transform brand attributes - use context for domain."""
        # Replace hardcoded domain with context
        if "domain" in attrs and isinstance(attrs["domain"], str):
            # Only replace if it's a concrete domain (not already using context)
            if not attrs["domain"].startswith("!"):
                attrs["domain"] = {"__CONTEXT__": "domain"}

        return attrs

    def transform_email_stage_attrs(self, attrs: Dict) -> Dict:
        """Transform email stage attributes - remap custom template paths.

        The staging export may use 'custom/' prefix for email templates, but
        the docker-compose deployment mounts templates under 'email/' (via
        ./authentik/custom-templates:/templates/email:ro). Remap so the
        blueprint matches the deployment mount point.
        """
        if "template" in attrs and isinstance(attrs["template"], str):
            template = attrs["template"]
            if template.startswith("custom/"):
                attrs["template"] = "email/" + template[len("custom/"):]
                self.log(f"Remapped email template: {template} -> {attrs['template']}")
        return attrs

    def clean_entry(self, entry: Dict) -> Dict:
        """Remove forbidden fields and convert references.

        Also adds 'id' field to custom entries for !KeyOf references.
        """
        model = entry.get("model", "")
        pk = str(entry.get("identifiers", {}).get("pk", ""))

        # First pass: convert and transform attrs
        original_attrs = entry.get("attrs", {})
        converted_attrs = self.convert_value(original_attrs, "attrs")

        # Apply model-specific transformations
        if model == "authentik_core.group":
            converted_attrs = self.transform_group_attrs(converted_attrs)
        elif model == "authentik_core.application":
            converted_attrs = self.transform_application_attrs(converted_attrs)
        elif model == "authentik_providers_oauth2.oauth2provider":
            converted_attrs = self.transform_oauth_provider_attrs(converted_attrs)
        elif model == "authentik_policies_expression.expressionpolicy":
            converted_attrs = self.transform_expression_policy_attrs(converted_attrs)
        elif model == "authentik_brands.brand":
            converted_attrs = self.transform_brand_attrs(converted_attrs)
        elif model == "authentik_stages_email.emailstage":
            converted_attrs = self.transform_email_stage_attrs(converted_attrs)

        # Remove forbidden fields from attrs recursively
        cleaned_attrs = self._remove_forbidden_fields(converted_attrs)

        # Second pass: build identifiers from transformed attrs
        cleaned = {}

        # Add 'id' field if this is a custom entry (for !KeyOf references)
        if pk and pk in self.pk_to_id:
            cleaned["id"] = self.pk_to_id[pk]

        for key, value in entry.items():
            if key == "identifiers":
                # Clean identifiers - remove pk, keep only semantic identifiers
                cleaned_identifiers = {}
                id_fields = self.IDENTIFIER_FIELDS.get(model, ["name"])

                # For bindings, identifiers should ALWAYS be built from attrs (target/stage/policy + order)
                if model in ["authentik_flows.flowstagebinding", "authentik_policies.policybinding"]:
                    for field in id_fields:
                        if field in cleaned_attrs:
                            # Already converted in cleaned_attrs
                            cleaned_identifiers[field] = cleaned_attrs[field]
                else:
                    # For other models, build identifiers from transformed attrs
                    for field in id_fields:
                        if field in cleaned_attrs:
                            cleaned_identifiers[field] = cleaned_attrs[field]
                        elif field in value and field not in self.FORBIDDEN_FIELDS:
                            cleaned_identifiers[field] = value[field]

                cleaned[key] = cleaned_identifiers

            elif key == "attrs":
                # Use already-processed attrs
                cleaned[key] = cleaned_attrs

            elif key in ["model", "state", "conditions", "permissions"]:
                # Keep as-is
                cleaned[key] = value

            else:
                # Skip unknown fields
                self.log(f"  Skipping unknown field: {key}")

        return cleaned

    def _remove_forbidden_fields(self, obj):
        """Recursively remove forbidden fields from a data structure."""
        if isinstance(obj, dict):
            return {
                k: self._remove_forbidden_fields(v)
                for k, v in obj.items()
                if k not in self.FORBIDDEN_FIELDS
            }
        elif isinstance(obj, list):
            return [self._remove_forbidden_fields(item) for item in obj]
        return obj

    def _remove_empty_collections(self, obj):
        """Recursively remove empty lists and dicts for cleaner output."""
        if isinstance(obj, dict):
            cleaned = {}
            for k, v in obj.items():
                # Recursively clean the value first
                cleaned_value = self._remove_empty_collections(v)
                # Only include if not an empty collection
                if not (isinstance(cleaned_value, (dict, list)) and len(cleaned_value) == 0):
                    cleaned[k] = cleaned_value
            return cleaned
        elif isinstance(obj, list):
            return [self._remove_empty_collections(item) for item in obj]
        return obj

    def should_skip_entry(self, entry: Dict) -> bool:
        """Determine if an entry should be excluded from the blueprint."""
        model = entry.get("model", "")
        attrs = entry.get("attrs", {})
        name = attrs.get("name", "")
        slug = attrs.get("slug", "")
        pk = entry.get("identifiers", {}).get("pk")

        # ALWAYS keep anything starting with "avatar-" (custom Avatar resources)
        if name.startswith("avatar-") or slug.startswith("avatar-"):
            self.log(f"  Keeping Avatar resource: {model} ({name or slug})")
            return False

        # Check if this entry is required as a dependency
        if pk and str(pk) in self.required_pks:
            self.log(f"  Keeping required dependency: {model} ({name or slug})")
            return False

        # ========================================================================
        # PHASE 1: MODEL-LEVEL FILTERS (entire model types to skip)
        # ========================================================================

        # Models to skip entirely (never needed in templates)
        SKIP_MODELS = {
            # Infrastructure (outposts, tokens, RBAC, scheduled tasks)
            'authentik_outposts.outpost',
            'authentik_outposts.kubernetesserviceconnection',
            'authentik_core.token',
            'authentik_rbac.role',
            'authentik_tasks_schedules.schedule',

            # Blueprint metadata (internal Authentik tracking)
            'authentik_blueprints.blueprintinstance',

            # Provider mappings (not used in OAuth2-only Avatar setup)
            'authentik_sources_ldap.ldapsourcepropertymapping',
            'authentik_providers_saml.samlpropertymapping',
            'authentik_sources_kerberos.kerberossourcepropertymapping',
            'authentik_providers_google_workspace.googleworkspaceprovidermapping',
            'authentik_providers_microsoft_entra.microsoftentraprovidermapping',
            'authentik_providers_scim.scimmapping',
            'authentik_providers_rac.racpropertymapping',

            # Notification system (default infrastructure)
            'authentik_events.notificationtransport',
            'authentik_events.notificationrule',
            'authentik_policies_event_matcher.eventmatcherpolicy',

            # Certificates (referenced via !Find, not created)
            'authentik_crypto.certificatekeypair',
        }

        if model in SKIP_MODELS:
            self.log(f"  Skipping unwanted model type: {model} ({name or slug or 'unnamed'})")
            return True

        # Skip user entries (users should not be in templates)
        if model == "authentik_core.user":
            self.log(f"  Skipping user entry: {name or attrs.get('username', 'unknown')}")
            return True

        # ========================================================================
        # PHASE 2: NAME-BASED FILTERS (keep only Avatar-specific entries)
        # ========================================================================

        # Skip group entries except Octopize groups
        if model == "authentik_core.group":
            if name not in ["Octopize - Admins", "Octopize - Users"]:
                self.log(f"  Skipping group entry: {name}")
                return True

        # Skip default Authentik flows (to avoid overriding newer defaults)
        # Keep custom flows (anything not starting with default-/authentik- or initial-setup)
        if model == "authentik_flows.flow":
            if slug.startswith(("default-", "authentik-")) or slug == "initial-setup":
                self.log(f"  Skipping default flow: {slug or name}")
                return True

        # Skip flow stage bindings for default flows
        # These will be managed by Authentik's default blueprints
        if model == "authentik_flows.flowstagebinding":
            target_pk = attrs.get("target")
            if target_pk:
                # Resolve the target PK to find which flow it binds to
                target_entry = self.pk_to_entry.get(str(target_pk))
                if target_entry and target_entry.get("model") == "authentik_flows.flow":
                    target_slug = target_entry.get("attrs", {}).get("slug", "")
                    if target_slug and (target_slug.startswith(("default-", "authentik-")) or target_slug == "initial-setup"):
                        self.log(f"  Skipping binding for default flow: {target_slug}")
                        return True

        # Expression policies - skip default/built-in policies
        if model == 'authentik_policies_expression.expressionpolicy':
            if name.lower().startswith(("default-", "authentik")):
                self.log(f"  Skipping default expression policy: {name}")
                return True

        # Password policies - skip default/built-in policies
        if model == 'authentik_policies_password.passwordpolicy':
            if name.lower().startswith(("default-", "authentik")):
                self.log(f"  Skipping default password policy: {name}")
                return True

        # OAuth2 scope mappings - keep only custom octopize:license
        if model == 'authentik_providers_oauth2.scopemapping':
            scope_name = attrs.get('scope_name', '')
            # Keep the custom octopize:license scope
            if scope_name == 'octopize:license':
                return False
            # Also check if name matches (in case scope_name field is different)
            if 'octopize' in name.lower() or 'license' in name.lower():
                return False
            # Skip all default Authentik OAuth mappings
            if name.startswith('authentik default'):
                self.log(f"  Skipping default OAuth scope mapping: {name}")
                return True

        # Skip default stages - they will be referenced via !Find and resolved from Authentik's defaults
        # Only keep Avatar-specific stages (those starting with "avatar-")
        stage_models = [
            "authentik_stages_email.emailstage",
            "authentik_stages_identification.identificationstage",
            "authentik_stages_password.passwordstage",
            "authentik_stages_prompt.prompt",
            "authentik_stages_prompt.promptstage",
            "authentik_stages_user_write.userwritestage",
            "authentik_stages_user_login.userloginstage",
            "authentik_stages_user_logout.userlogoutstage",
            "authentik_stages_consent.consentstage",
            "authentik_stages_authenticator_static.authenticatorstaticstage",
            "authentik_stages_authenticator_totp.authenticatortotpstage",
            "authentik_stages_authenticator_validate.authenticatorvalidatestage",
            "authentik_stages_authenticator_webauthn.authenticatorwebauthnstage",
        ]

        if model in stage_models:
            # Skip default/built-in stages (default ones will be resolved via !Find)
            if name.lower().startswith(("default-", "authentik")):
                # default-recovery-* stages come from an optional example blueprint
                # (not auto-loaded) — keep them so they're created by our blueprint
                if any(name.lower().startswith(p) for p in self.REQUIRED_DEFAULT_STAGE_PREFIXES):
                    self.log(f"  Keeping non-auto-loaded default stage: {name}")
                    return False
                self.log(f"  Skipping default stage: {name or '(unnamed)'}")
                return True

            # Skip specific initial-setup prompts (Section 10 requirement)
            if model == "authentik_stages_prompt.prompt":
                skip_prompts = [
                    "initial-setup-field-password-repeat",
                    "initial-setup-field-header",
                    "initial-setup-field-email",
                ]
                if name in skip_prompts:
                    self.log(f"  Skipping initial-setup prompt: {name}")
                    return True

            # Skip specific initial-setup prompt stages
            if model == "authentik_stages_prompt.promptstage":
                skip_stages = [
                    "stage-default-oobe-password",
                    "Change your password",
                ]
                if name in skip_stages:
                    self.log(f"  Skipping initial-setup prompt stage: {name}")
                    return True

            # Keep custom stages (those starting with "avatar-")

        # ========================================================================
        # PHASE 3: ATTRIBUTE-BASED FILTERS
        # ========================================================================

        # Policy bindings - skip bindings for default policies
        if model == 'authentik_policies.policybinding':
            policy_ref = attrs.get('policy')
            # If policy is a string UUID, try to resolve it
            if isinstance(policy_ref, str) and self.UUID_PATTERN.match(policy_ref):
                policy_entry = self.pk_to_entry.get(policy_ref)
                if policy_entry:
                    policy_name = policy_entry.get('attrs', {}).get('name', '')
                    if policy_name.lower().startswith(("default-", "authentik")):
                        self.log(f"  Skipping binding for default policy: {policy_name}")
                        return True

        # Brands - keep only Avatar brand with context variables
        if model == 'authentik_brands.brand':
            domain = attrs.get('domain', '')
            branding_title = attrs.get('branding_title', '')
            # Keep if it uses context variables or has Avatar branding
            if branding_title == 'Avatar':
                return False
            # Skip if it's a concrete domain (not using !Context)
            if isinstance(domain, str) and domain and not domain.startswith('!'):
                self.log(f"  Skipping concrete brand domain: {domain}")
                return True

        return False

    def generate_context(self) -> Dict:
        """Generate the context section with dynamic variables.

        IMPORTANT: Context values must be plain values (strings), NOT !Context
        self-references. The context block defines defaults that can be overridden
        when creating a blueprint instance. Using !Context tags here would create
        circular self-references (e.g. domain: !Context [domain, ...] looks up
        'domain' in this same context dict, finding itself → infinite recursion).

        Entries in the blueprint reference these via !Context 'key_name'.
        """
        return {
            "app_name": "Avatar API",
            "domain": "[[DOMAIN]]",
            "license_type": "full",
        }

    def _create_section_header(self, title: str, sub_header: bool = False) -> str:
        """Create a formatted section header comment.

        Args:
            title: Header text
            sub_header: If True, creates a sub-section header (shorter separator)

        Returns:
            Formatted header string with newlines
        """
        if sub_header:
            separator = "=" * 40
            return f"\n  # {separator}\n  # {title}\n  # {separator}\n"
        else:
            separator = "=" * 60
            return f"\n# {separator}\n# {title}\n# {separator}\n"

    def _group_entries_by_section(self, entries: List[Dict]) -> List[Tuple[str, List[Dict], bool]]:
        """Group entries by section based on ENTRY_GROUPS configuration.

        Args:
            entries: List of blueprint entries

        Returns:
            List of (section_name, section_entries, requires_sub_grouping) tuples
        """
        grouped_sections = []
        used_entries = set()

        for section_name, model_patterns, requires_sub_grouping in self.ENTRY_GROUPS:
            section_entries = []
            for i, entry in enumerate(entries):
                if i in used_entries:
                    continue
                model = entry.get("model", "")
                if model in model_patterns:
                    section_entries.append(entry)
                    used_entries.add(i)

            if section_entries:
                grouped_sections.append((section_name, section_entries, requires_sub_grouping))

        # Collect any remaining entries not matched by patterns
        remaining_entries = [entry for i, entry in enumerate(entries) if i not in used_entries]
        if remaining_entries:
            grouped_sections.append(("OTHER", remaining_entries, False))

        return grouped_sections

    def _get_flow_name_from_pk(self, flow_pk: str) -> str:
        """Get human-readable flow name from PK for sub-grouping."""
        entry = self.pk_to_entry.get(str(flow_pk))
        if entry:
            slug = entry.get("attrs", {}).get("slug", "")
            # Convert slug to title case: "avatar-authentication-flow" -> "Authentication Flow"
            if slug.startswith("avatar-"):
                slug = slug[7:]  # Remove "avatar-" prefix
            return " ".join(word.capitalize() for word in slug.replace("-", " ").split())
        return "Unknown Flow"

    def _sub_group_entries(self, section_name: str, entries: List[Dict]) -> List[Tuple[str, List[Dict]]]:
        """Sub-group entries based on section type.

        Args:
            section_name: Name of the section being processed
            entries: List of entries to sub-group

        Returns:
            List of (sub_group_name, sub_group_entries) tuples
        """
        if section_name == "FLOW STAGE BINDINGS":
            return self._sub_group_flow_bindings(entries)
        else:
            # Default: no sub-grouping, return all entries in one group
            return [(section_name, entries)]

    def _sub_group_flow_bindings(self, bindings: List[Dict]) -> List[Tuple[str, List[Dict]]]:
        """Sub-group flow stage bindings by target flow.

        Args:
            bindings: List of flowstagebinding entries

        Returns:
            List of (flow_name, bindings_for_flow) tuples
        """
        # Group bindings by target flow
        flow_groups = {}
        for binding in bindings:
            attrs = binding.get("attrs", {})
            target = attrs.get("target")

            # Extract flow name from target (could be KeyOfTag, FindTag, UUID string, int, or marker dict)
            if isinstance(target, KeyOfTag):
                # Extract from KeyOfTag - the id_ref is the flow's id (e.g., "avatar-authentication-flow")
                id_ref = target.id_ref
                flow_name = " ".join(word.capitalize() for word in id_ref.replace("avatar-", "").replace("-", " ").split())
            elif isinstance(target, FindTag):
                # Extract from FindTag object
                identifiers = target.identifiers
                if isinstance(identifiers, list) and len(identifiers) >= 2:
                    # Get slug from identifiers [slug, value]
                    slug = identifiers[1]
                    flow_name = " ".join(word.capitalize() for word in slug.replace("avatar-", "").replace("-", " ").split())
                else:
                    flow_name = "Unknown Flow"
            elif isinstance(target, dict) and "__KEYOF__" in target:
                # Extract from !KeyOf marker dict
                id_ref = target["__KEYOF__"]
                flow_name = " ".join(word.capitalize() for word in id_ref.replace("avatar-", "").replace("-", " ").split())
            elif isinstance(target, dict) and "__FIND__" in target:
                # Extract from !Find marker dict (shouldn't happen after tag conversion, but handle it)
                find_data = target["__FIND__"]
                if isinstance(find_data, list) and len(find_data) >= 2:
                    identifiers = find_data[1]
                    if isinstance(identifiers, list) and len(identifiers) >= 2:
                        # Get slug from identifiers [slug, value]
                        slug = identifiers[1]
                        flow_name = " ".join(word.capitalize() for word in slug.replace("avatar-", "").replace("-", " ").split())
                    else:
                        flow_name = "Unknown Flow"
                else:
                    flow_name = "Unknown Flow"
            elif isinstance(target, (str, int)):
                flow_name = self._get_flow_name_from_pk(str(target))
            else:
                flow_name = "Unknown Flow"

            if flow_name not in flow_groups:
                flow_groups[flow_name] = []
            flow_groups[flow_name].append(binding)

        # Sort by flow name for consistent output
        # Return with full sub-header names
        return [(f"FLOW STAGE BINDINGS - {flow_name}", entries) for flow_name, entries in sorted(flow_groups.items())]

    # Mapping from [[PLACEHOLDER]] names to !Env variable names
    ENV_PLACEHOLDERS = {
        "DOMAIN": "AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN",
        "CLIENT_ID": "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_ID",
        "CLIENT_SECRET": "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_SECRET",
        "API_REDIRECT_URI": "AVATAR_AUTHENTIK_BLUEPRINT_API_REDIRECT_URI",
        "SELF_SERVICE_LICENSE": "AVATAR_AUTHENTIK_BLUEPRINT_SELF_SERVICE_LICENSE",
    }

    def _convert_to_env_placeholders(self, obj):
        """Convert [[PLACEHOLDER]] format to !Env tags.

        Replaces [[PLACEHOLDER]] strings with EnvTag markers that will be
        serialized as !Env AVATAR_AUTHENTIK_BLUEPRINT_<NAME> in the output YAML.
        This allows authentik to resolve the values from environment variables
        at blueprint apply time.

        Args:
            obj: Any YAML structure (dict, list, string, etc.)

        Returns:
            The same structure with placeholders converted to !Env tags
        """
        if isinstance(obj, str):
            import re
            # Check if the entire string is a single placeholder like [[DOMAIN]]
            match = re.fullmatch(r'\[\[([A-Z_]+)\]\]', obj)
            if match:
                placeholder = match.group(1)
                env_var = self.ENV_PLACEHOLDERS.get(placeholder)
                if env_var:
                    return EnvTag(env_var)
                # Unknown placeholder - leave as-is
                return obj
            # Check if the string contains placeholders embedded in other text
            # e.g. "https://[[DOMAIN]]/api" - for these, use !Format with !Env
            if re.search(r'\[\[[A-Z_]+\]\]', obj):
                # Replace each [[PLACEHOLDER]] with a %s and collect the env vars
                parts = re.split(r'\[\[([A-Z_]+)\]\]', obj)
                if len(parts) == 3 and parts[0] == '' and parts[2] == '':
                    # Whole string was a single placeholder (shouldn't reach here but safety)
                    env_var = self.ENV_PLACEHOLDERS.get(parts[1])
                    if env_var:
                        return EnvTag(env_var)
                # Build a !Format with !Env args
                format_str = ""
                env_args = []
                for i, part in enumerate(parts):
                    if i % 2 == 0:
                        # Literal text
                        format_str += part
                    else:
                        # Placeholder name
                        format_str += "%s"
                        env_var = self.ENV_PLACEHOLDERS.get(part)
                        if env_var:
                            env_args.append(EnvTag(env_var))
                        else:
                            env_args.append(f"[[{part}]]")
                return FormatTag(format_str, env_args)
            return obj
        elif isinstance(obj, dict):
            return {k: self._convert_to_env_placeholders(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_env_placeholders(item) for item in obj]
        elif isinstance(obj, (FindTag, ContextTag, FormatTag, KeyOfTag)):
            if isinstance(obj, FindTag):
                return FindTag(
                    self._convert_to_env_placeholders(obj.model),
                    self._convert_to_env_placeholders(obj.identifiers)
                )
            elif isinstance(obj, ContextTag):
                # In helm mode, convert context defaults that use [[PLACEHOLDER]]
                return ContextTag(
                    self._convert_to_env_placeholders(obj.name),
                    self._convert_to_env_placeholders(obj.default)
                )
            elif isinstance(obj, FormatTag):
                return FormatTag(
                    self._convert_to_env_placeholders(obj.template),
                    self._convert_to_env_placeholders(obj.args)
                )
            elif isinstance(obj, KeyOfTag):
                return KeyOfTag(
                    self._convert_to_env_placeholders(obj.id_ref)
                )
        return obj

    def clean_metadata(self, metadata: Dict) -> Dict:
        """Clean up metadata - remove generated labels and set proper name."""
        cleaned = {}

        # Remove 'labels' field entirely
        for key, value in metadata.items():
            if key == "labels":
                continue  # Skip labels
            elif key == "name":
                # Replace with template name
                cleaned[key] = "octopize-avatar-sso-configuration"
            else:
                cleaned[key] = value

        # If name wasn't present, add it
        if "name" not in cleaned:
            cleaned["name"] = "octopize-avatar-sso-configuration"

        return cleaned

    def convert_blueprint(self, blueprint: Dict) -> Dict:
        """Convert entire blueprint from PK to !Find references.

        Args:
            blueprint: Input blueprint data

        Returns:
            Converted blueprint
        """
        self.log("Starting blueprint conversion")

        # Build PK index first
        self.build_pk_index(blueprint)

        # NOTE: Dependency tracking disabled - default stages are referenced by !Find,
        # so they will be resolved from Authentik's default blueprints at runtime.
        # Uncomment the line below to keep default stages/flows as dependencies:
        # self.identify_custom_flows_and_dependencies(blueprint)

        converted = {
            "version": blueprint.get("version", 1),
            "metadata": self.clean_metadata(blueprint.get("metadata", {})),
            "context": self.generate_context(),
            "entries": [],
        }

        # Convert each entry
        skipped = 0
        regular_entries = []
        application_entries = []
        brand_entries = []

        for i, entry in enumerate(blueprint.get("entries", [])):
            model = entry.get("model", "unknown")

            # Skip unwanted entries (users, non-Octopize groups, etc.)
            if self.should_skip_entry(entry):
                skipped += 1
                continue

            # Extract name/slug for logging
            attrs = entry.get("attrs", {})
            name = attrs.get("name", "")
            slug = attrs.get("slug", "")
            identifier = slug or name or "(unnamed)"

            self.log(f"Converting entry {i+1}: {model} ({identifier})")
            cleaned = self.clean_entry(entry)
            # Remove empty collections for cleaner output
            cleaned = self._remove_empty_collections(cleaned)

            # Sort entries by type for proper ordering
            if model == "authentik_core.application":
                application_entries.append(cleaned)
            elif model == "authentik_brands.brand":
                brand_entries.append(cleaned)
            else:
                regular_entries.append(cleaned)

        # Combine entries: regular entries, then applications, then brands
        converted["entries"] = regular_entries + application_entries + brand_entries

        # Clean top-level context as well
        converted["context"] = self._remove_empty_collections(converted["context"])

        self.log(f"Conversion complete: {len(converted['entries'])} entries ({skipped} skipped)")
        return converted


def validate_blueprint(output_path: Path, script_path: Path) -> bool:
    """Run the validation script on the output blueprint."""
    print(f"\n{'='*60}")
    print("Running validation...")
    print(f"{'='*60}\n")

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), str(output_path)],
            capture_output=True,
            text=True,
        )

        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode == 0:
            print("\n✅ Validation PASSED")
            return True
        else:
            print("\n❌ Validation FAILED")
            return False

    except Exception as e:
        print(f"❌ Validation failed with error: {e}", file=sys.stderr)
        return False
