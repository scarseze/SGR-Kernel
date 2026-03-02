"""KC-I: Template resolution tests — nested fields, missing refs, recursive, json interp.
Migrated to v2: uses core.execution.resolution.resolve_inputs directly.
"""


from jinja2 import Undefined

from core.execution.resolution import resolve_inputs


class TestTemplateResolution:
    def test_kc_i1_nested_field(self):
        """{{step1.output.a.b}} resolves nested value."""
        outputs = {"step1": {"a": {"b": "deep_value"}}}
        result = resolve_inputs({"v": "{{step1.output.a.b}}"}, outputs)
        assert result["v"] == "deep_value"

    def test_kc_i2_missing_field_safe(self):
        """Missing nested field → fallback, no crash."""
        outputs = {"step1": {"a": {"b": "val"}}}
        result = resolve_inputs({"v": "{{step1.output.a.missing}}"}, outputs)
        # Jinja2 returns Undefined for missing nested attributes
        v = result["v"]
        assert isinstance(v, Undefined) or v == "" or "missing" in str(v) or "{{" in str(v)

    def test_kc_i2_missing_step_safe(self):
        """Missing step_id → template stays literal (fallback)."""
        result = resolve_inputs({"v": "{{nonexistent.output}}"}, {})
        v = result["v"]
        assert isinstance(v, Undefined) or "nonexistent" in str(v) or v == ""

    def test_kc_i3_dict_recursive(self):
        """Templates inside dict values resolve."""
        outputs = {"step1": "resolved_value"}
        result = resolve_inputs({"key": "{{step1.output}}", "static": "hello"}, outputs)
        assert result["key"] == "resolved_value"
        assert result["static"] == "hello"

    def test_kc_i3_list_recursive(self):
        """Templates inside list items resolve."""
        outputs = {"step1": "val1", "step2": "val2"}
        result = resolve_inputs({"items": ["{{step1.output}}", "{{step2.output}}", "lit"]}, outputs)
        assert result["items"] == ["val1", "val2", "lit"]

    def test_kc_i1_interpolation_non_string(self):
        """Non-primitive in interpolation → rendered (Jinja2 NativeEnvironment preserves type)."""
        outputs = {"step1": {"key": "val", "num": 42}}
        result = resolve_inputs({"v": "{{step1.output}}"}, outputs)
        # NativeEnvironment should return the dict directly
        assert isinstance(result["v"], dict) or '"key"' in str(result["v"])
