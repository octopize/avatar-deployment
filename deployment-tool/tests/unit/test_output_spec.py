"""Tests for OutputSpec."""

from octopize_avatar_deploy.output_spec import OutputSpec


class TestOutputSpec:
    def test_creation(self):
        spec = OutputSpec("template.txt", "output.txt")
        assert spec.template_name == "template.txt"
        assert spec.output_path == "output.txt"

    def test_equality(self):
        a = OutputSpec("a.template", "a.out")
        b = OutputSpec("a.template", "a.out")
        assert a == b

    def test_inequality(self):
        a = OutputSpec("a.template", "a.out")
        b = OutputSpec("b.template", "b.out")
        assert a != b
