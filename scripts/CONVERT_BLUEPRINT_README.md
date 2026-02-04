# Authentik Blueprint Converter

## Overview

The `convert-blueprint-to-find.py` script converts Authentik blueprint exports from primary key (PK) references to declarative `!Find` lookups, making blueprints portable and versionable.

## Usage

```bash
# Basic conversion
python scripts/convert-blueprint-to-find.py input.yaml output.yaml

# With validation
python scripts/convert-blueprint-to-find.py input.yaml output.yaml --validate

# With verbose logging
python scripts/convert-blueprint-to-find.py input.yaml output.yaml --validate --verbose
```

## What It Does

### Transforms
1. **Removes primary keys**: Strips `pk:` fields from identifiers
2. **Removes managed fields**: Eliminates `managed:` flags from attrs
3. **Converts UUID references**: Replaces UUID-based foreign key references with `!Find` lookups
4. **Builds semantic identifiers**: Creates identifiers based on model-specific meaningful fields (e.g., `name`, `slug`)
5. **Filters unwanted entries**: Intelligently removes Authentik defaults and system infrastructure

### Intelligent Filtering (NEW - 2026-02-04)

The converter now includes **comprehensive filtering** to produce clean, Avatar-specific blueprints:

**Phase 1: Model-Level Filters** (removes entire categories)
- System infrastructure: outposts, tokens, RBAC roles, scheduled tasks
- Blueprint metadata: internal Authentik tracking (28 entries)
- Provider mappings: LDAP, SAML, Kerberos, Google, Microsoft, SCIM, RAC (32 entries)
- Notification system: transports, rules, event matchers (9 entries)
- Certificates: referenced via `!Find`, not created

**Phase 2: Name-Based Filters** (Avatar-specific only)
- Expression policies: keep only `avatar-*` prefix
- Password policies: keep only `avatar-*` prefix
- OAuth2 scopes: keep only `octopize:license` custom scope
- Stages/prompts: keep only `avatar-*` prefix

**Phase 3: Attribute-Based Filters** (conditional)
- Policy bindings: keep only bindings to Avatar policies
- Brands: keep only Avatar brand (not concrete domains)
- Groups: keep only "Octopize - Admins" and "Octopize - Users"
- Flows: keep only avatar-authentication-flow, avatar-self-service-signup-flow, avatar-recovery-flow

**Result**: Reduces output from ~165 entries to ~33 entries (80% reduction), matching the target blueprint structure.

### Example Transformation

**Before (raw export)**:
```yaml
- model: authentik_flows.flow
  identifiers:
    pk: c21e4ccf-6dde-4cc7-b0c4-6cd85c394734
  attrs:
    name: avatar-authentication-flow
    slug: avatar-authentication-flow

- model: authentik_stages_identification.identificationstage
  identifiers:
    pk: a1b2c3d4-e5f6-7890-abcd-ef1234567890
  attrs:
    name: avatar-authentication-stage
    enrollment_flow: c21e4ccf-6dde-4cc7-b0c4-6cd85c394734
```

**After (converted)**:
```yaml
- model: authentik_flows.flow
  identifiers:
    slug: avatar-authentication-flow
  attrs:
    name: avatar-authentication-flow
    slug: avatar-authentication-flow

- model: authentik_core.group
  identifiers:
    name: Octopize - Admins
  attrs:
    name: Octopize - Admins
    is_superuser: true

- model: authentik_stages_identification.identificationstage
  identifiers:
    name: avatar-authentication-stage
  attrs:
    name: avatar-authentication-stage
    enrollment_flow: !Find
    - authentik_flows.flow
    - - slug
      - avatar-authentication-flow
```

**Note**: User entries and non-Octopize groups are automatically filtered out during conversion as they should not be in blueprint templates. The converter also filters ~132 additional default Authentik entries including system infrastructure, provider mappings, scheduled tasks, and default policies/stages.

## Supported Models

The converter includes identifier mappings for common Authentik models:

- **Flows**: `authentik_flows.flow` (by `slug`)
- **Stages**: Various stage types (by `name`)
- **Policies**: Various policy types (by `name`)
- **Providers**: OAuth2, SAML, Proxy, etc. (by `name`)
- **Applications**: `authentik_core.application` (by `slug`)
- **Groups**: `authentik_core.group` (by `name`)
- **Users**: `authentik_core.user` (by `username`)
- **Bindings**: Flow stage bindings and policy bindings (by `target`, `stage`/`policy`, and `order`)

See the `IDENTIFIER_FIELDS` dict in the script for the complete list.

## Validation

The `--validate` flag runs `validate-authentik-blueprint.py` on the output to ensure:

- No primary keys (`pk:`) remain
- No `managed:` flags remain
- No blueprint-level IDs remain
- UUID references are converted to `!Find` lookups
- No user entries are present
- Only Octopize groups (Octopize - Admins, Octopize - Users) are present
- No unwanted system infrastructure or default Authentik entries

**Example Output**:
```
✅ Conversion complete: output.yaml
   Processed 33 entries (132 skipped)

✅ All validations passed
```

## Known Limitations

1. **System-generated identifiers**: Some Authentik-generated identifiers contain UUIDs (e.g., `ak-outpost-f4cbfc64-...-api`). These are preserved as they're part of the identifier string, not references.

2. **Unknown models**: Models not in `IDENTIFIER_FIELDS` default to using `name` as the identifier field.

3. **Recursive references**: Complex nested references (e.g., policy bindings targeting flow stage bindings) are supported but may result in deeply nested `!Find` structures.

4. **Filtering behavior**: The converter is optimized for Avatar SSO deployments. It filters out:
   - All user entries
   - Non-Octopize groups  
   - All default Authentik flows (except avatar-* flows)
   - System infrastructure (outposts, tokens, certificates, RBAC roles)
   - Provider mappings for non-OAuth2 protocols (LDAP, SAML, Kerberos, etc.)
   - Default policies, stages, and prompts (except avatar-* prefixed ones)
   - Blueprint metadata and scheduled tasks
   - Notification system defaults

   If you need different filtering behavior, modify the `should_skip_entry()` method in the script.

## Adding Support for New Models

To add support for a new Authentik model:

1. Identify the semantic identifier field(s) (usually `name`, `slug`, or similar)
2. Add an entry to `IDENTIFIER_FIELDS` in the script:
   ```python
   "authentik_your_app.yourmodel": ["identifier_field"],
   ```
3. For composite identifiers (like bindings), use a list:
   ```python
   "authentik_flows.flowstagebinding": ["target", "stage", "order"],
   ```

## Integration with validate-authentik-blueprint.py

The validator has been updated to accept a blueprint path argument:

```bash
# Validate default blueprint
python scripts/validate-authentik-blueprint.py

# Validate specific blueprint
python scripts/validate-authentik-blueprint.py path/to/blueprint.yaml
```

## Development Workflow

1. Export blueprint from Authentik UI
2. Run converter: `python scripts/convert-blueprint-to-find.py export.yaml template.yaml --validate --verbose`
3. Review validation output
4. Manually add placeholders (e.g., `[[DOMAIN]]`) where needed
5. Test import in Authentik

## See Also

- [validate-authentik-blueprint.py](validate-authentik-blueprint.py) - Blueprint validation tool
- [docker/templates/authentik/octopize-avatar-blueprint.yaml](../docker/templates/authentik/octopize-avatar-blueprint.yaml) - Example converted blueprint
- [Authentik Blueprint Documentation](https://goauthentik.io/docs/developer-docs/blueprints/)
