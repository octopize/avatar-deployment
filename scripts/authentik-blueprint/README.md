# authentik-blueprint-export

Convert Authentik blueprint exports from primary key (pk) references to declarative `!Find` lookups, enabling portable and versionable blueprints.

## Installation

```bash
# Install with uv
uv tool install .

# Or install in development mode
uv pip install -e ".[dev]"
```

## Usage

```bash
# Basic usage
authentik-blueprint-export input.yaml output.yaml

# With validation
authentik-blueprint-export input.yaml output.yaml --validate

# With verbose output
authentik-blueprint-export input.yaml output.yaml --validate --verbose
```

### Using uv tool run

```bash
# Run without installing
uv tool run authentik-blueprint-export input.yaml output.yaml
```

## What It Does

- Removes `pk` and `managed` fields
- Converts UUID references to `!Find` lookups
- Builds semantic identifiers (e.g., by `name`, `slug`)
- Recursively converts nested references
- Filters out user entries and non-Octopize groups
- Adds context variables for templating
- Uses correct `!Context` syntax (scalar for references, sequence for definitions)

## Development

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run tests
uv run pytest

# Run specific test
uv run pytest tests/test_converter.py::TestBlueprintConverter::test_sample_conversion -v
```

## Context Tag Syntax

The converter generates correct Authentik blueprint syntax:

```yaml
# Context definitions (with defaults) - use sequence notation
context:
  app_name: !Context [app_name, Avatar API]
  domain: !Context [domain, '[[DOMAIN]]']
  
# Context references (without defaults) - use scalar notation
entries:
  - attrs:
      license: !Context license_type
      url: !Format ['https://%s/api', !Context domain]
```

## Testing

See [tests/README.md](tests/README.md) for test documentation.
