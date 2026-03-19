"""Tests for CLI output helpers."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    import pytest

from notebooklm.cli._output import output_json


class SampleModel(BaseModel):
    """Test model for output_json."""

    model_config = ConfigDict(frozen=True)
    name: str
    value: int


class TestOutputJson:
    """output_json のテスト。"""

    def test_正常系_dictをJSONとして出力(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        output_json({"key": "value"})
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == {"key": "value"}

    def test_正常系_PydanticモデルをJSONとして出力(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        model = SampleModel(name="test", value=42)
        output_json(model)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == {"name": "test", "value": 42}

    def test_正常系_モデルリストをJSONとして出力(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        models = [SampleModel(name="a", value=1), SampleModel(name="b", value=2)]
        output_json(models)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 2
        assert data[0]["name"] == "a"

    def test_正常系_日本語がエスケープされない(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        output_json({"名前": "テスト"})
        captured = capsys.readouterr()
        assert "テスト" in captured.out
        assert "\\u" not in captured.out
