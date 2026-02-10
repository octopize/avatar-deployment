#!/usr/bin/env python3
"""Integration tests for the Authentik blueprint converter."""

import tempfile
from pathlib import Path

import pytest
import yaml
from authentik_blueprint.converter import BlueprintConverter, KeyOfTag, EnvTag, FormatTag

# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"
STAGING_EXPORT = Path(__file__).parent.parent.parent.parent / "docker" / "authentik" / "blueprints" / "staging-export.yaml"
EXPECTED_OUTPUT = FIXTURES_DIR / "expected-output.yaml"
INPUT_SAMPLE = FIXTURES_DIR / "input-sample.yaml"
EXPECTED_SAMPLE = FIXTURES_DIR / "expected-sample.yaml"


@pytest.fixture
def converter():
    """Create a converter instance."""
    return BlueprintConverter(verbose=False)


class TestBlueprintConverter:
    """Integration tests for blueprint conversion."""

    def test_sample_conversion(self, converter):
        """Test converting a small sample input (fast smoke test)."""
        # Skip if fixture doesn't exist
        if not INPUT_SAMPLE.exists():
            pytest.skip(f"Input sample file not found: {INPUT_SAMPLE}")

        # Load the input
        blueprint = converter.load_blueprint(INPUT_SAMPLE)

        # Convert
        converted = converter.convert_blueprint(blueprint)

        # Save to temporary file for comparison
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            converter.save_blueprint(converted, tmp_path)

        try:
            # Load both files for comparison
            with open(tmp_path) as f:
                actual = yaml.safe_load(f)

            with open(EXPECTED_SAMPLE) as f:
                expected = yaml.safe_load(f)

            # Compare structure
            assert actual.keys() == expected.keys(), "Top-level keys don't match"
            assert actual['version'] == expected['version'], "Version mismatch"
            assert actual['metadata'] == expected['metadata'], "Metadata mismatch"
            assert actual['context'] == expected['context'], "Context mismatch"

            # Compare entries
            assert len(actual['entries']) == len(expected['entries']), \
                f"Entry count mismatch: {len(actual['entries'])} vs {len(expected['entries'])}"

            # Compare each entry
            for i, (actual_entry, expected_entry) in enumerate(zip(actual['entries'], expected['entries'])):
                assert actual_entry == expected_entry, \
                    f"Entry {i} mismatch:\nActual: {actual_entry}\nExpected: {expected_entry}"

        finally:
            # Clean up temp file
            tmp_path.unlink()

    def test_staging_export_conversion(self, converter):
        """Test that converting staging-export produces the expected output."""
        # Skip if staging-export doesn't exist
        if not STAGING_EXPORT.exists():
            pytest.skip(f"Staging export file not found: {STAGING_EXPORT}")

        # Load the input
        blueprint = converter.load_blueprint(STAGING_EXPORT)

        # Convert
        converted = converter.convert_blueprint(blueprint)

        # Save to temporary file for comparison
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            converter.save_blueprint(converted, tmp_path)

        try:
            # Load both files for comparison
            with open(tmp_path) as f:
                actual = yaml.safe_load(f)

            if not EXPECTED_OUTPUT.exists():
                pytest.skip(f"Expected output file not found: {EXPECTED_OUTPUT}")

            with open(EXPECTED_OUTPUT) as f:
                expected = yaml.safe_load(f)

            # Compare structure
            assert actual.keys() == expected.keys(), "Top-level keys don't match"
            assert actual['version'] == expected['version'], "Version mismatch"
            assert actual['metadata'] == expected['metadata'], "Metadata mismatch"
            assert actual['context'] == expected['context'], "Context mismatch"

            # Compare entries
            assert len(actual['entries']) == len(expected['entries']), \
                f"Entry count mismatch: {len(actual['entries'])} vs {len(expected['entries'])}"

            # Compare each entry
            for i, (actual_entry, expected_entry) in enumerate(zip(actual['entries'], expected['entries'])):
                assert actual_entry == expected_entry, \
                    f"Entry {i} mismatch:\nActual: {actual_entry}\nExpected: {expected_entry}"

        finally:
            # Clean up temp file
            tmp_path.unlink()

    def test_context_tag_scalar_notation(self, converter):
        """Test that context section has plain values and entries use !Context scalar notation."""
        if not EXPECTED_OUTPUT.exists():
            pytest.skip(f"Expected output file not found: {EXPECTED_OUTPUT}")

        # Read raw YAML text (not parsed)
        with open(EXPECTED_OUTPUT) as f:
            yaml_text = f.read()

        # Context section should have plain values (NOT !Context self-references)
        # This prevents infinite recursion when authentik resolves the context block
        assert "context:\n  app_name: Avatar API" in yaml_text, \
            "Context section should have plain string values, not !Context tags"
        assert "  domain: !Env AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN" in yaml_text, \
            "Context section should use !Env tags for environment variables"
        assert "  license_type: full" in yaml_text, \
            "Context section should have plain string values"

        # Entries should reference context via !Context scalar notation
        assert "!Context 'license_type'" in yaml_text or "!Context license_type" in yaml_text, \
            "Entry context references should use scalar notation"
        assert "!Context 'domain'" in yaml_text or "!Context domain" in yaml_text, \
            "Entry context references should use scalar notation"
        assert "!Context 'app_name'" in yaml_text or "!Context app_name" in yaml_text, \
            "Entry context references should use scalar notation"

    def test_no_pk_or_managed_fields(self, converter):
        """Test that converted output has no pk or managed fields."""
        if not EXPECTED_OUTPUT.exists():
            pytest.skip(f"Expected output file not found: {EXPECTED_OUTPUT}")

        with open(EXPECTED_OUTPUT) as f:
            data = yaml.safe_load(f)

        def check_no_forbidden_fields(obj, path=""):
            """Recursively check for forbidden fields."""
            if isinstance(obj, dict):
                for key in ['pk', 'managed']:
                    assert key not in obj, f"Found forbidden field '{key}' at {path}"
                for k, v in obj.items():
                    check_no_forbidden_fields(v, f"{path}.{k}" if path else k)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_no_forbidden_fields(item, f"{path}[{i}]")

        check_no_forbidden_fields(data)

    def test_find_tags_generated(self, converter):
        """Test that UUID/integer references are converted to !Find tags."""
        if not EXPECTED_OUTPUT.exists():
            pytest.skip(f"Expected output file not found: {EXPECTED_OUTPUT}")

        with open(EXPECTED_OUTPUT) as f:
            yaml_text = f.read()

        # Should contain !Find tags
        assert "!Find" in yaml_text, "Output should contain !Find tags"

        # Load and check structure
        with open(EXPECTED_OUTPUT) as f:
            data = yaml.safe_load(f)

        # Count !Find usage (they become dicts with specific structure after loading)
        # Note: This is a basic check - full validation would require custom YAML loader

    def test_keyof_tag_class(self):
        """Test KeyOfTag class creation and representation."""
        tag = KeyOfTag("avatar-authentication-flow")
        assert tag.id_ref == "avatar-authentication-flow"
        assert repr(tag) == "KeyOfTag('avatar-authentication-flow')"

    def test_keyof_tag_equality(self):
        """Test KeyOfTag equality comparison."""
        tag1 = KeyOfTag("avatar-authentication-flow")
        tag2 = KeyOfTag("avatar-authentication-flow")
        tag3 = KeyOfTag("avatar-recovery-flow")

        assert tag1 == tag2
        assert tag1 != tag3
        assert tag1 != "avatar-authentication-flow"  # Different type

    def test_keyof_yaml_serialization(self, converter):
        """Test that KeyOfTag serializes correctly to YAML."""
        tag = KeyOfTag("avatar-authentication-flow")

        # Serialize to YAML
        yaml_output = yaml.dump({"target": tag}, default_flow_style=False)

        assert "!KeyOf" in yaml_output
        assert "avatar-authentication-flow" in yaml_output

    def test_entry_groups_order(self, converter):
        """Test that ENTRY_GROUPS are in correct dependency order."""
        group_names = [name for name, _, _ in converter.ENTRY_GROUPS]

        # Verify critical orderings:
        # 1. Flows before Flow Stage Bindings
        flows_idx = group_names.index("FLOWS")
        bindings_idx = group_names.index("FLOW STAGE BINDINGS")
        assert flows_idx < bindings_idx, "FLOWS must come before FLOW STAGE BINDINGS"

        # 2. Stages before Flow Stage Bindings
        stages_idx = group_names.index("STAGES")
        assert stages_idx < bindings_idx, "STAGES must come before FLOW STAGE BINDINGS"

        # 3. Prompts before Stages (prompts are used by prompt stages)
        prompts_idx = group_names.index("PROMPTS")
        assert prompts_idx < stages_idx, "PROMPTS must come before STAGES"

        # 4. Policies before Policy Bindings
        policies_idx = group_names.index("POLICIES")
        policy_bindings_idx = group_names.index("POLICY BINDINGS")
        assert policies_idx < policy_bindings_idx, "POLICIES must come before POLICY BINDINGS"

        # 5. OAuth Provider before Application
        provider_idx = group_names.index("OAUTH PROVIDER")
        app_idx = group_names.index("APPLICATION")
        assert provider_idx < app_idx, "OAUTH PROVIDER must come before APPLICATION"

        # 6. Application before Brand
        brand_idx = group_names.index("BRAND")
        assert app_idx < brand_idx, "APPLICATION must come before BRAND"

    def test_custom_entry_detection(self, converter):
        """Test that custom entries are detected correctly."""
        # Build a small test blueprint
        test_blueprint = {
            "version": 1,
            "entries": [
                {
                    "model": "authentik_flows.flow",
                    "identifiers": {"pk": "11111111-1111-1111-1111-111111111111"},
                    "attrs": {"slug": "avatar-authentication-flow", "name": "Avatar Auth"}
                },
                {
                    "model": "authentik_flows.flow",
                    "identifiers": {"pk": "22222222-2222-2222-2222-222222222222"},
                    "attrs": {"slug": "default-authentication-flow", "name": "Default Auth"}
                },
                {
                    "model": "authentik_stages_identification.identificationstage",
                    "identifiers": {"pk": "33333333-3333-3333-3333-333333333333"},
                    "attrs": {"name": "avatar-authentication-stage"}
                },
            ]
        }

        converter.build_pk_index(test_blueprint)

        # avatar- prefixed should be custom
        assert "11111111-1111-1111-1111-111111111111" in converter.custom_entry_pks
        assert "33333333-3333-3333-3333-333333333333" in converter.custom_entry_pks

        # default- prefixed should NOT be custom
        assert "22222222-2222-2222-2222-222222222222" not in converter.custom_entry_pks

    def test_id_generation(self, converter):
        """Test that IDs are generated correctly for custom entries."""
        test_blueprint = {
            "version": 1,
            "entries": [
                {
                    "model": "authentik_flows.flow",
                    "identifiers": {"pk": "11111111-1111-1111-1111-111111111111"},
                    "attrs": {"slug": "avatar-authentication-flow", "name": "Avatar Auth"}
                },
                {
                    "model": "authentik_stages_identification.identificationstage",
                    "identifiers": {"pk": "22222222-2222-2222-2222-222222222222"},
                    "attrs": {"name": "avatar-authentication-stage"}
                },
            ]
        }

        converter.build_pk_index(test_blueprint)

        # Check generated IDs
        assert converter.pk_to_id.get("11111111-1111-1111-1111-111111111111") == "avatar-authentication-flow"
        assert converter.pk_to_id.get("22222222-2222-2222-2222-222222222222") == "avatar-authentication-stage"

    def test_id_generation_bindings(self, converter):
        """Test that binding entries get descriptive composite IDs instead of UUIDs."""
        test_blueprint = {
            "version": 1,
            "entries": [
                {
                    "model": "authentik_flows.flow",
                    "identifiers": {"pk": "11111111-1111-1111-1111-111111111111"},
                    "attrs": {"slug": "avatar-auth-flow", "name": "Avatar Auth"}
                },
                {
                    "model": "authentik_stages_identification.identificationstage",
                    "identifiers": {"pk": "22222222-2222-2222-2222-222222222222"},
                    "attrs": {"name": "avatar-identification-stage"}
                },
                {
                    "model": "authentik_policies_expression.expressionpolicy",
                    "identifiers": {"pk": "44444444-4444-4444-4444-444444444444"},
                    "attrs": {"name": "avatar-my-policy"}
                },
                {
                    "model": "authentik_flows.flowstagebinding",
                    "identifiers": {"pk": "33333333-3333-3333-3333-333333333333"},
                    "attrs": {
                        "target": "11111111-1111-1111-1111-111111111111",
                        "stage": "22222222-2222-2222-2222-222222222222",
                        "order": 10,
                    }
                },
                {
                    "model": "authentik_policies.policybinding",
                    "identifiers": {"pk": "55555555-5555-5555-5555-555555555555"},
                    "attrs": {
                        "target": "33333333-3333-3333-3333-333333333333",
                        "policy": "44444444-4444-4444-4444-444444444444",
                        "order": 0,
                    }
                },
            ]
        }

        converter.build_pk_index(test_blueprint)

        # flowstagebinding should have composite id: flow-slug-bind-stage-name-order-N
        fsb_id = converter.pk_to_id.get("33333333-3333-3333-3333-333333333333")
        assert fsb_id == "avatar-auth-flow-bind-avatar-identification-stage-order-10"

        # policybinding target is the flowstagebinding (no slug/name),
        # so it falls back to the binding's generated id
        pb_id = converter.pk_to_id.get("55555555-5555-5555-5555-555555555555")
        assert pb_id == "avatar-my-policy-bind-avatar-auth-flow-bind-avatar-identification-stage-order-10-order-0"

    def test_keyof_conversion(self, converter):
        """Test that custom entry references are converted to !KeyOf."""
        test_blueprint = {
            "version": 1,
            "entries": [
                {
                    "model": "authentik_flows.flow",
                    "identifiers": {"pk": "11111111-1111-1111-1111-111111111111"},
                    "attrs": {"slug": "avatar-authentication-flow", "name": "Avatar Auth"}
                },
            ]
        }

        converter.build_pk_index(test_blueprint)

        # Convert a UUID reference to the custom entry
        result = converter.convert_value("11111111-1111-1111-1111-111111111111", "target")

        # Should be a __KEYOF__ marker
        assert "__KEYOF__" in result
        assert result["__KEYOF__"] == "avatar-authentication-flow"

    def test_staging_export_has_keyof_tags(self, converter):
        """Test that staging export conversion produces !KeyOf tags for custom entries."""
        if not STAGING_EXPORT.exists():
            pytest.skip(f"Staging export file not found: {STAGING_EXPORT}")

        # Load and convert
        blueprint = converter.load_blueprint(STAGING_EXPORT)
        converted = converter.convert_blueprint(blueprint)

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            converter.save_blueprint(converted, tmp_path)

        try:
            with open(tmp_path) as f:
                yaml_text = f.read()

            # Should have both !KeyOf (for custom entries) and !Find (for default entries)
            assert "!KeyOf" in yaml_text, "Output should contain !KeyOf tags for custom entries"

            # Should still have !Find for default objects
            # (like default-authentication-login stage)
            assert "!Find" in yaml_text, "Output should contain !Find tags for default entries"

        finally:
            tmp_path.unlink()


class TestEnvTag:
    """Tests for the EnvTag class and Helm mode."""

    def test_env_tag_class(self):
        """Test EnvTag class creation and representation."""
        tag = EnvTag("AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN")
        assert tag.var_name == "AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN"
        assert tag.default is None
        assert repr(tag) == "EnvTag('AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN', None)"

    def test_env_tag_with_default(self):
        """Test EnvTag class with a default value."""
        tag = EnvTag("AVATAR_AUTHENTIK_BLUEPRINT_SELF_SERVICE_LICENSE", "full")
        assert tag.var_name == "AVATAR_AUTHENTIK_BLUEPRINT_SELF_SERVICE_LICENSE"
        assert tag.default == "full"

    def test_env_tag_equality(self):
        """Test EnvTag equality comparison."""
        tag1 = EnvTag("MY_VAR")
        tag2 = EnvTag("MY_VAR")
        tag3 = EnvTag("OTHER_VAR")

        assert tag1 == tag2
        assert tag1 != tag3
        assert tag1 != "MY_VAR"  # Different type

    def test_env_tag_yaml_serialization_scalar(self):
        """Test that EnvTag without default serializes as scalar: !Env var_name."""
        tag = EnvTag("AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN")
        yaml_output = yaml.dump({"domain": tag}, default_flow_style=False)

        assert "!Env" in yaml_output
        assert "AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN" in yaml_output
        # Scalar form should NOT have brackets
        assert "[" not in yaml_output

    def test_env_tag_yaml_serialization_with_default(self):
        """Test that EnvTag with default serializes as sequence: !Env [var, default]."""
        tag = EnvTag("AVATAR_AUTHENTIK_BLUEPRINT_SELF_SERVICE_LICENSE", "full")
        yaml_output = yaml.dump({"license": tag}, default_flow_style=False)

        assert "!Env" in yaml_output
        assert "AVATAR_AUTHENTIK_BLUEPRINT_SELF_SERVICE_LICENSE" in yaml_output
        assert "full" in yaml_output

    def test_convert_to_env_simple_placeholder(self):
        """Test that [[PLACEHOLDER]] strings are converted to EnvTag."""
        converter = BlueprintConverter(verbose=False)
        result = converter._convert_to_env_placeholders("[[DOMAIN]]")

        assert isinstance(result, EnvTag)
        assert result.var_name == "AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN"

    def test_convert_to_env_all_placeholders(self):
        """Test that all known placeholders are converted."""
        converter = BlueprintConverter(verbose=False)

        mapping = {
            "[[DOMAIN]]": "AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN",
            "[[CLIENT_ID]]": "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_ID",
            "[[CLIENT_SECRET]]": "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_SECRET",
            "[[API_REDIRECT_URI]]": "AVATAR_AUTHENTIK_BLUEPRINT_API_REDIRECT_URI",
            "[[SELF_SERVICE_LICENSE]]": "AVATAR_AUTHENTIK_BLUEPRINT_SELF_SERVICE_LICENSE",
        }

        for placeholder, expected_env in mapping.items():
            result = converter._convert_to_env_placeholders(placeholder)
            assert isinstance(result, EnvTag), f"Expected EnvTag for {placeholder}"
            assert result.var_name == expected_env, f"Expected {expected_env} for {placeholder}"

    def test_convert_to_env_no_placeholder(self):
        """Test that strings without placeholders are left unchanged."""
        converter = BlueprintConverter(verbose=False)
        result = converter._convert_to_env_placeholders("just a normal string")
        assert result == "just a normal string"

    def test_convert_to_env_dict(self):
        """Test that dicts are recursively processed."""
        converter = BlueprintConverter(verbose=False)
        result = converter._convert_to_env_placeholders({
            "domain": "[[DOMAIN]]",
            "name": "Avatar API",
        })

        assert isinstance(result["domain"], EnvTag)
        assert result["domain"].var_name == "AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN"
        assert result["name"] == "Avatar API"

    def test_convert_to_env_list(self):
        """Test that lists are recursively processed."""
        converter = BlueprintConverter(verbose=False)
        result = converter._convert_to_env_placeholders(["[[CLIENT_ID]]", "keep-this"])

        assert isinstance(result[0], EnvTag)
        assert result[0].var_name == "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_ID"
        assert result[1] == "keep-this"

    def test_convert_to_env_context_section(self):
        """Test that context values with [[PLACEHOLDER]] become !Env tags."""
        converter = BlueprintConverter(verbose=False)
        context = {
            "app_name": "Avatar API",
            "domain": "[[DOMAIN]]",
            "license_type": "full",
        }
        result = converter._convert_to_env_placeholders(context)

        assert result["app_name"] == "Avatar API"
        assert isinstance(result["domain"], EnvTag)
        assert result["domain"].var_name == "AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN"
        assert result["license_type"] == "full"

    def test_env_marker_to_tag(self):
        """Test that __ENV__ markers are converted to EnvTag objects."""
        converter = BlueprintConverter(verbose=False)
        result = converter._convert_markers_to_tags({"__ENV__": "MY_VAR"})

        assert isinstance(result, EnvTag)
        assert result.var_name == "MY_VAR"

    def test_env_marker_to_tag_with_default(self):
        """Test that __ENV__ markers with defaults are converted correctly."""
        converter = BlueprintConverter(verbose=False)
        result = converter._convert_markers_to_tags({"__ENV__": ["MY_VAR", "default-value"]})

        assert isinstance(result, EnvTag)
        assert result.var_name == "MY_VAR"
        assert result.default == "default-value"

    def test_save_produces_env_tags(self):
        """Test that save_blueprint produces !Env tags in output."""
        converter = BlueprintConverter(verbose=False)

        # Create a minimal blueprint with placeholders
        blueprint = {
            "version": 1,
            "metadata": {"name": "test-blueprint"},
            "context": {
                "domain": "[[DOMAIN]]",
                "app_name": "Avatar API",
            },
            "entries": [
                {
                    "model": "authentik_providers_oauth2.oauth2provider",
                    "identifiers": {"name": "test-provider"},
                    "attrs": {
                        "client_id": "[[CLIENT_ID]]",
                        "client_secret": "[[CLIENT_SECRET]]",
                    }
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            converter.save_blueprint(blueprint, tmp_path)

        try:
            with open(tmp_path) as f:
                yaml_text = f.read()

            # Should contain !Env tags
            assert "!Env" in yaml_text, "Helm output should contain !Env tags"
            assert "AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN" in yaml_text
            assert "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_ID" in yaml_text
            assert "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_SECRET" in yaml_text

            # Should NOT contain [[PLACEHOLDER]] format
            assert "[[DOMAIN]]" not in yaml_text
            assert "[[CLIENT_ID]]" not in yaml_text
            assert "[[CLIENT_SECRET]]" not in yaml_text

            # Should have the header mentioning env variables
            assert "environment variables" in yaml_text

        finally:
            tmp_path.unlink()

    def test_save_header(self):
        """Test that save_blueprint uses the correct header."""
        converter = BlueprintConverter(verbose=False)

        blueprint = {
            "version": 1,
            "metadata": {"name": "test"},
            "context": {},
            "entries": [],
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            converter.save_blueprint(blueprint, tmp_path)

        try:
            with open(tmp_path) as f:
                yaml_text = f.read()

            assert "AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN" in yaml_text
            assert "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_ID" in yaml_text
            assert "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_SECRET" in yaml_text
            assert "AVATAR_AUTHENTIK_BLUEPRINT_API_REDIRECT_URI" in yaml_text
            assert "AVATAR_AUTHENTIK_BLUEPRINT_SELF_SERVICE_LICENSE" in yaml_text

        finally:
            tmp_path.unlink()

    def test_env_placeholders_constant(self):
        """Test that ENV_PLACEHOLDERS mapping covers all expected keys."""
        expected_keys = {"DOMAIN", "CLIENT_ID", "CLIENT_SECRET", "API_REDIRECT_URI", "SELF_SERVICE_LICENSE"}
        assert set(BlueprintConverter.ENV_PLACEHOLDERS.keys()) == expected_keys

        # All env vars should be prefixed with AVATAR_AUTHENTIK_
        for env_var in BlueprintConverter.ENV_PLACEHOLDERS.values():
            assert env_var.startswith("AVATAR_AUTHENTIK_BLUEPRINT_"), \
                f"Env var {env_var} should start with AVATAR_AUTHENTIK_BLUEPRINT_"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
