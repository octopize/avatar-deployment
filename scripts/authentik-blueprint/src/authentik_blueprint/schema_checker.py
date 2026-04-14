"""AST-based blueprint schema checker.

Validates blueprint field values against Authentik model field choices extracted
directly from the Authentik source tree. No Django, no database, no containers.

The Authentik source is shallow-cloned at the required version (cached in /tmp)
or pointed at an existing checkout via --authentik-root.
"""

import ast
import subprocess
import sys
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Blueprint YAML loading — unknown custom tags become skip sentinels
# ---------------------------------------------------------------------------

class _SkipValue:
    """Placeholder for !Env, !KeyOf, !Context, etc. — not validated."""


_SKIP = _SkipValue()


def _skip_constructor(loader, tag_suffix, node):
    return _SKIP


def _make_blueprint_loader():
    loader = type("_BlueprintLoader", (yaml.SafeLoader,), {})
    loader.add_multi_constructor("", _skip_constructor)
    return loader


def load_blueprint(path: Path) -> dict:
    with path.open() as f:
        return yaml.load(f, Loader=_make_blueprint_loader())


# ---------------------------------------------------------------------------
# AST extraction helpers
# ---------------------------------------------------------------------------

def _const_str(node) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def extract_text_choices(py_file: Path) -> dict[str, list[str]]:
    """Return {ClassName: [value, ...]} for every TextChoices subclass in the file."""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return {}

    result: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        is_choices = any(
            (isinstance(b, ast.Attribute) and b.attr in ("TextChoices", "IntegerChoices"))
            or (isinstance(b, ast.Name) and b.id in ("TextChoices", "IntegerChoices"))
            for b in node.bases
        )
        if not is_choices:
            continue
        values: list[str] = []
        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            val = item.value
            # PLAIN = "plain", _("Plain")  →  Tuple(Constant("plain"), ...)
            if isinstance(val, ast.Tuple) and val.elts:
                s = _const_str(val.elts[0])
                if s is not None:
                    values.append(s)
            else:
                s = _const_str(val)
                if s is not None:
                    values.append(s)
        if values:
            result[node.name] = values
    return result


def extract_field_choices_refs(py_file: Path) -> dict[str, dict[str, str]]:
    """Return {ModelClass: {field_name: ChoicesClassName}} for fields with choices=X.choices."""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return {}

    result: dict[str, dict[str, str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        model_name = node.name
        for item in ast.walk(node):
            if not isinstance(item, ast.Assign):
                continue
            if not (len(item.targets) == 1 and isinstance(item.targets[0], ast.Name)):
                continue
            field_name = item.targets[0].id
            if not isinstance(item.value, ast.Call):
                continue
            for kw in item.value.keywords:
                if kw.arg != "choices":
                    continue
                if (
                    isinstance(kw.value, ast.Attribute)
                    and kw.value.attr == "choices"
                    and isinstance(kw.value.value, ast.Name)
                ):
                    result.setdefault(model_name, {})[field_name] = kw.value.value.id
    return result


def extract_app_label_map(authentik_root: Path) -> dict[str, str]:
    """Return {app_label: python_module_path} by AST-parsing all apps.py files."""
    mapping: dict[str, str] = {}
    for apps_py in authentik_root.rglob("apps.py"):
        try:
            tree = ast.parse(apps_py.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            label = name = None
            for item in node.body:
                if not isinstance(item, ast.Assign):
                    continue
                if not (len(item.targets) == 1 and isinstance(item.targets[0], ast.Name)):
                    continue
                attr = item.targets[0].id
                s = _const_str(item.value)
                if s is not None:
                    if attr == "label":
                        label = s
                    elif attr == "name":
                        name = s
            if label and name:
                mapping[label] = name
    return mapping


# ---------------------------------------------------------------------------
# Schema builder
# ---------------------------------------------------------------------------

def build_schema(authentik_root: Path, verbose: bool = False) -> dict[str, dict[str, dict[str, list[str]]]]:
    """
    Build a nested schema from AST analysis of the source tree:
        {app_label: {model_name_lower: {field_name: [valid_values]}}}
    """
    app_labels = extract_app_label_map(authentik_root)

    all_choices: dict[str, list[str]] = {}
    field_refs: dict[str, dict[str, dict[str, str]]] = {}  # rel_path → {ModelClass → {field → ChoicesClass}}

    for py_file in authentik_root.rglob("*.py"):
        rel = str(py_file.relative_to(authentik_root))
        tc = extract_text_choices(py_file)
        fc = extract_field_choices_refs(py_file)
        all_choices.update(tc)
        if fc:
            field_refs[rel] = fc

    schema: dict[str, dict[str, dict[str, list[str]]]] = {}
    for app_label, module_path in app_labels.items():
        # module_path is e.g. "authentik.sources.oauth"; files are relative to authentik/
        inner_path = module_path.removeprefix("authentik.").replace(".", "/")
        models_rel = inner_path + "/models.py"
        if models_rel not in field_refs:
            continue
        for model_class, fields in field_refs[models_rel].items():
            model_key = model_class.lower()
            for field_name, choices_class in fields.items():
                if choices_class not in all_choices:
                    continue
                schema.setdefault(app_label, {}).setdefault(model_key, {})[field_name] = all_choices[choices_class]
                if verbose:
                    vals = all_choices[choices_class]
                    print(f"  schema: {app_label}.{model_key}.{field_name} → {vals}")
    return schema


# ---------------------------------------------------------------------------
# Clone / locate the Authentik source tree
# ---------------------------------------------------------------------------

def ensure_authentik_root(version: str | None, root: Path | None, verbose: bool) -> Path:
    if root is not None:
        if not root.exists():
            print(f"❌ --authentik-root path does not exist: {root}", file=sys.stderr)
            sys.exit(1)
        return root

    if version is None:
        print("❌ Provide --authentik-version or --authentik-root", file=sys.stderr)
        sys.exit(1)

    cache_dir = Path(f"/tmp/authentik-{version}")
    if cache_dir.exists():
        if verbose:
            print(f"→ Using cached clone at {cache_dir}")
        return cache_dir

    tag = f"version/{version}"
    print(f"→ Shallow-cloning authentik {tag} into {cache_dir} …")
    result = subprocess.run(
        ["git", "clone", "--depth=1", "--branch", tag,
         "https://github.com/goauthentik/authentik.git", str(cache_dir)],
        capture_output=not verbose,
    )
    if result.returncode != 0:
        print(f"❌ git clone failed (exit {result.returncode})", file=sys.stderr)
        if not verbose:
            print(result.stderr.decode(), file=sys.stderr)
        sys.exit(1)

    return cache_dir


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def validate_blueprint(blueprint: dict, schema: dict, verbose: bool) -> list[str]:
    """Return a list of error strings for field choice violations."""
    errors: list[str] = []
    entries = blueprint.get("entries", [])

    for i, entry in enumerate(entries):
        model_ref = entry.get("model", "")
        if not model_ref or isinstance(model_ref, _SkipValue):
            continue

        parts = model_ref.split(".", 1)
        if len(parts) != 2:
            continue
        app_label, model_name = parts[0], parts[1].lower()

        model_schema = schema.get(app_label, {}).get(model_name, {})
        if not model_schema:
            continue

        entry_id = entry.get("id", f"entry[{i}]")
        attrs = entry.get("attrs", {}) or {}

        for field_name, valid_values in model_schema.items():
            raw = attrs.get(field_name)
            # Only validate plain string values. Anything else (!Env, !KeyOf,
            # !Context etc.) resolves at runtime and cannot be checked statically.
            if not isinstance(raw, str):
                continue
            value = str(raw)
            if value not in valid_values:
                errors.append(
                    f"Entry {i} ({model_ref}, id={entry_id!r}): "
                    f"field {field_name!r} has value {value!r}, "
                    f"which is not a valid choice. Valid values: {valid_values}"
                )
            elif verbose:
                print(f"  OK  entry {i} ({entry_id}): {field_name}={value!r}")

    return errors


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(
    blueprint: Path,
    authentik_version: str | None = None,
    authentik_root: Path | None = None,
    verbose: bool = False,
) -> bool:
    """
    Run the schema check. Returns True if the blueprint passes, False otherwise.
    """
    authentik_root = ensure_authentik_root(authentik_version, authentik_root, verbose)

    print(f"→ Building schema from {authentik_root} …")
    schema = build_schema(authentik_root / "authentik", verbose=verbose)
    total_fields = sum(len(f) for m in schema.values() for f in m.values())
    print(f"  {len(schema)} apps, {total_fields} constrained fields found")

    print(f"→ Validating {blueprint} …")
    data = load_blueprint(blueprint)
    errors = validate_blueprint(data, schema, verbose=verbose)

    if errors:
        print(f"\n❌ {len(errors)} field choice violation(s) found:\n")
        for e in errors:
            print(f"  {e}")
        return False

    print("✅ All blueprint field choices are valid.")
    return True
