"""Tests for the generic config/prompt system."""

from octopize_avatar_deploy.steps.base import (
    PromptConfig,
    ValidationError,
    ValidationSuccess,
    make_path_validator,
    parse_bool,
    parse_int,
    parse_str,
)


class TestValidationParsers:
    """Test the standard parser/validator functions."""

    def test_parse_bool_from_bool(self):
        """Test parsing boolean from bool type."""
        result = parse_bool(True)
        assert isinstance(result, ValidationSuccess)
        assert result.value is True

        result = parse_bool(False)
        assert isinstance(result, ValidationSuccess)
        assert result.value is False

    def test_parse_bool_from_string(self):
        """Test parsing boolean from string values."""
        # True values
        for value in ["true", "TRUE", "True", "yes", "YES", "1", "on", "enabled"]:
            result = parse_bool(value)
            assert isinstance(result, ValidationSuccess), f"Failed for {value}"
            assert result.value is True

        # False values
        for value in ["false", "FALSE", "False", "no", "NO", "0", "off", "disabled"]:
            result = parse_bool(value)
            assert isinstance(result, ValidationSuccess), f"Failed for {value}"
            assert result.value is False

    def test_parse_bool_from_int(self):
        """Test parsing boolean from integer values."""
        result = parse_bool(1)
        assert isinstance(result, ValidationSuccess)
        assert result.value is True

        result = parse_bool(0)
        assert isinstance(result, ValidationSuccess)
        assert result.value is False

    def test_parse_bool_invalid(self):
        """Test parsing boolean from invalid values."""
        result = parse_bool("invalid")
        assert isinstance(result, ValidationError)
        assert "Cannot parse as boolean" in result.message

        result = parse_bool(42)
        assert isinstance(result, ValidationError)

    def test_parse_int_from_int(self):
        """Test parsing int from int type."""
        result = parse_int(42)
        assert isinstance(result, ValidationSuccess)
        assert result.value == 42

    def test_parse_int_from_string(self):
        """Test parsing int from string values."""
        result = parse_int("123")
        assert isinstance(result, ValidationSuccess)
        assert result.value == 123

        result = parse_int("  456  ")
        assert isinstance(result, ValidationSuccess)
        assert result.value == 456

    def test_parse_int_invalid(self):
        """Test parsing int from invalid values."""
        result = parse_int("not a number")
        assert isinstance(result, ValidationError)
        assert "Cannot parse as integer" in result.message

    def test_parse_str(self):
        """Test parsing string (always succeeds)."""
        result = parse_str("hello")
        assert isinstance(result, ValidationSuccess)
        assert result.value == "hello"

        result = parse_str(123)
        assert isinstance(result, ValidationSuccess)
        assert result.value == "123"

    def test_make_path_validator_must_exist(self, tmp_path):
        """Test path validator with must_exist requirement."""
        validator = make_path_validator(must_exist=True)

        # Existing path should pass
        existing_file = tmp_path / "exists.txt"
        existing_file.touch()
        result = validator(str(existing_file))
        assert isinstance(result, ValidationSuccess)

        # Non-existing path should fail
        result = validator(str(tmp_path / "does_not_exist.txt"))
        assert isinstance(result, ValidationError)
        assert "does not exist" in result.message.lower()

    def test_make_path_validator_must_be_dir(self, tmp_path):
        """Test path validator with must_be_dir requirement."""
        validator = make_path_validator(must_exist=True, must_be_dir=True)

        # Directory should pass
        existing_dir = tmp_path / "mydir"
        existing_dir.mkdir()
        result = validator(str(existing_dir))
        assert isinstance(result, ValidationSuccess)

        # File should fail
        existing_file = tmp_path / "myfile.txt"
        existing_file.touch()
        result = validator(str(existing_file))
        assert isinstance(result, ValidationError)
        assert "not a directory" in result.message.lower()

    def test_make_path_validator_must_be_file(self, tmp_path):
        """Test path validator with must_be_file requirement."""
        validator = make_path_validator(must_exist=True, must_be_file=True)

        # File should pass
        existing_file = tmp_path / "myfile.txt"
        existing_file.touch()
        result = validator(str(existing_file))
        assert isinstance(result, ValidationSuccess)

        # Directory should fail
        existing_dir = tmp_path / "mydir"
        existing_dir.mkdir()
        result = validator(str(existing_dir))
        assert isinstance(result, ValidationError)
        assert "not a file" in result.message.lower()

    def test_make_path_validator_tilde_expansion(self, tmp_path, monkeypatch):
        """Test path validator expands tilde."""
        monkeypatch.setenv("HOME", str(tmp_path))
        validator = make_path_validator(must_exist=False)

        result = validator("~/test.txt")
        assert isinstance(result, ValidationSuccess)
        # The result should contain the expanded path string
        assert result.value == "~/test.txt"  # Returns original string


class TestPromptConfig:
    """Test the PromptConfig dataclass."""

    def test_prompt_config_basic(self):
        """Test basic PromptConfig creation."""
        config = PromptConfig(
            config_key="TEST_KEY",
            prompt_message="Enter value",
            default_value="default",
            prompt_key="test.key",
        )

        assert config.config_key == "TEST_KEY"
        assert config.prompt_message == "Enter value"
        assert config.default_value == "default"
        assert config.prompt_key == "test.key"
        assert config.prompt_function is None
        assert config.parse_and_validate is None

    def test_prompt_config_with_parser(self):
        """Test PromptConfig with parse_and_validate function."""
        config = PromptConfig(
            config_key="ENABLE_FEATURE",
            prompt_message="Enable feature?",
            default_value=True,
            parse_and_validate=parse_bool,
        )

        assert config.parse_and_validate is not None
        # Test that the parser works
        result = config.parse_and_validate(True)
        assert isinstance(result, ValidationSuccess)
        assert result.value is True
