"""KC-H: StepResult contract tests — structured output, wrapping, trace preview.
Migrated to v2: uses resolve_inputs and direct StepResult unit tests.
"""

import json

import pytest

from core.result import StepResult
from core.types import StepStatus


class TestStepResultContract:
    def test_kc_h1_data_stored(self):
        """KC-H1: StepResult.data stores structured data."""
        data = {"key": "value", "nested": [1, 2, 3]}
        result = StepResult(data=data, output_text="Summary")
        assert result.data == data
        assert result.output_text == "Summary"

    def test_kc_h2_string_auto_wrapped(self):
        """KC-H2: str → auto-wrapped in StepResult."""
        # In v2, SkillRuntimeAdapter wraps raw strings
        result = StepResult(data="plain string", output_text="plain string")
        assert isinstance(result, StepResult)
        assert result.data == "plain string"
        assert result.status == StepStatus.COMPLETED

    def test_trace_preview_json(self):
        """trace_preview uses json.dumps for dict data."""
        r = StepResult(data={"key": "val"}, output_text="hi")
        parsed = json.loads(r.trace_preview())
        assert parsed["key"] == "val"

    def test_trace_preview_string(self):
        """trace_preview returns raw string for str data."""
        r = StepResult(data="hello", output_text="hello")
        assert r.trace_preview() == "hello"

    def test_trace_preview_truncated(self):
        """trace_preview respects max_len."""
        r = StepResult(data="x" * 5000, output_text="big")
        assert len(r.trace_preview(max_len=100)) == 100
