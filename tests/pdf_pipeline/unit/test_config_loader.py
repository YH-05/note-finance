"""Unit tests for pdf_pipeline.config.loader module."""

from __future__ import annotations

from pathlib import Path

import pytest

from pdf_pipeline.config.loader import load_config
from pdf_pipeline.exceptions import ConfigError
from pdf_pipeline.types import PipelineConfig


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_正常系_有効なYAMLからPipelineConfigを生成(self, tmp_path: Path) -> None:
        yaml_content = """\
llm:
  provider: "anthropic"
  model: "claude-opus-4-5"
  max_tokens: 4096
  temperature: 0.0

noise_filter:
  min_chunk_chars: 50
  skip_patterns: []

input_dirs:
  - "data/raw/pdfs"

output_dir: "data/processed"
batch_size: 10
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        config = load_config(config_file)

        assert isinstance(config, PipelineConfig)
        assert config.llm.provider == "anthropic"
        assert config.llm.model == "claude-opus-4-5"
        assert config.llm.max_tokens == 4096
        assert config.noise_filter.min_chunk_chars == 50
        assert config.input_dirs == [Path("data/raw/pdfs")]
        assert config.output_dir == Path("data/processed")
        assert config.batch_size == 10

    def test_正常系_input_dirsのみ指定でデフォルト値を使用(
        self, tmp_path: Path
    ) -> None:
        yaml_content = """\
input_dirs:
  - "data/raw"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        config = load_config(config_file)

        assert isinstance(config, PipelineConfig)
        assert config.input_dirs == [Path("data/raw")]
        assert config.llm.provider == "anthropic"
        assert config.batch_size > 0

    def test_正常系_複数input_dirsを含むYAMLを正しくパース(
        self, tmp_path: Path
    ) -> None:
        yaml_content = """\
input_dirs:
  - "data/raw/pdfs"
  - "data/extra/pdfs"
batch_size: 5
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        config = load_config(config_file)

        assert len(config.input_dirs) == 2
        assert config.input_dirs[0] == Path("data/raw/pdfs")
        assert config.input_dirs[1] == Path("data/extra/pdfs")
        assert config.batch_size == 5

    def test_異常系_ファイルが存在しない場合にConfigError(self) -> None:
        with pytest.raises(ConfigError, match="not found"):
            load_config(Path("/nonexistent/path/config.yaml"))

    def test_異常系_ディレクトリパスを指定した場合にConfigError(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ConfigError, match="not a file"):
            load_config(tmp_path)

    def test_異常系_不正なYAML構文でConfigError(self, tmp_path: Path) -> None:
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("key: [invalid yaml", encoding="utf-8")

        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_config(config_file)

    def test_異常系_YAMLルートがマッピングでない場合にConfigError(
        self, tmp_path: Path
    ) -> None:
        config_file = tmp_path / "list.yaml"
        config_file.write_text("- item1\n- item2\n", encoding="utf-8")

        with pytest.raises(ConfigError, match="mapping"):
            load_config(config_file)

    def test_異常系_input_dirsが空リストでConfigError(self, tmp_path: Path) -> None:
        yaml_content = """\
input_dirs: []
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="validation failed"):
            load_config(config_file)

    def test_異常系_input_dirsが欠落でConfigError(self, tmp_path: Path) -> None:
        yaml_content = """\
llm:
  provider: "anthropic"
batch_size: 10
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="validation failed"):
            load_config(config_file)

    def test_異常系_batch_sizeが0以下でConfigError(self, tmp_path: Path) -> None:
        yaml_content = """\
input_dirs:
  - "data/raw"
batch_size: 0
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="validation failed"):
            load_config(config_file)

    def test_正常系_実際の設定ファイルをロードできる(self) -> None:
        config_path = Path("data/config/pdf-pipeline-config.yaml")
        if not config_path.exists():
            pytest.skip("Actual config file not present")

        config = load_config(config_path)

        assert len(config.input_dirs) >= 1
        assert config.batch_size > 0
