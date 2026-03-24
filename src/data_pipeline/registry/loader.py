"""Registry loader: JSON設定ファイルの読み込み・バリデーション.

統合インデックス（source_registry.json）と収集方法定義（collection_methods.json）を
ロードし、整合性チェックを行う。
"""

from __future__ import annotations

import json
from pathlib import Path

from data_pipeline.registry.models import (
    CollectionMethodDef,
    CollectionMethodRegistry,
    DataSource,
    SourceRegistry,
    ValidationIssue,
)

# AIDEV-NOTE: data_paths パッケージが利用可能な場合は get_config_dir() を使う。
# 利用不可の場合はフォールバックとしてプロジェクトルートから解決する。
try:
    from data_paths import get_config_dir

    _CONFIG_DIR: Path | None = get_config_dir()
except ImportError:
    _CONFIG_DIR = None

_SOURCE_REGISTRY_FILE = "source_registry.json"
_COLLECTION_METHODS_FILE = "collection_methods.json"


def _resolve_config_dir(config_dir: Path | None = None) -> Path:
    """設定ディレクトリを解決する."""
    if config_dir is not None:
        return config_dir
    if _CONFIG_DIR is not None:
        return _CONFIG_DIR
    # フォールバック: pyproject.toml があるディレクトリから探す
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent / "data" / "config"
    msg = "Cannot resolve config directory. Set config_dir or DATA_ROOT."
    raise FileNotFoundError(msg)


class RegistryLoader:
    """統合レジストリローダー.

    Parameters
    ----------
    config_dir : Path | None
        設定ディレクトリのパス。None の場合は data_paths.get_config_dir() を使用。

    Examples
    --------
    >>> loader = RegistryLoader()
    >>> registry = loader.load_source_registry()
    >>> print(len(registry.sources))
    27
    >>> disconnected = registry.get_disconnected()
    >>> for s in disconnected:
    ...     print(f"{s.source_id}: {s.notes}")
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = _resolve_config_dir(config_dir)

    def load_collection_methods(self) -> CollectionMethodRegistry:
        """収集方法定義をロードする.

        Returns
        -------
        CollectionMethodRegistry
            収集方法のレジストリ。

        Raises
        ------
        FileNotFoundError
            collection_methods.json が見つからない場合。
        """
        path = self.config_dir / _COLLECTION_METHODS_FILE
        if not path.exists():
            msg = f"Collection methods file not found: {path}"
            raise FileNotFoundError(msg)

        with path.open(encoding="utf-8") as f:
            raw = json.load(f)

        methods = {}
        for method_id, method_data in raw.get("methods", {}).items():
            method_data["method_id"] = method_id
            methods[method_id] = CollectionMethodDef(**method_data)

        return CollectionMethodRegistry(
            version=raw.get("version", "1.0"),
            methods=methods,
        )

    def load_source_registry(self) -> SourceRegistry:
        """ソースレジストリをロードする.

        Returns
        -------
        SourceRegistry
            全データソースのレジストリ。

        Raises
        ------
        FileNotFoundError
            source_registry.json が見つからない場合。
        """
        path = self.config_dir / _SOURCE_REGISTRY_FILE
        if not path.exists():
            msg = f"Source registry file not found: {path}"
            raise FileNotFoundError(msg)

        with path.open(encoding="utf-8") as f:
            raw = json.load(f)

        sources = [DataSource(**s) for s in raw.get("sources", [])]
        return SourceRegistry(
            version=raw.get("version", "1.0"),
            updated_at=raw.get("updated_at", ""),
            sources=sources,
        )

    def validate(self) -> list[ValidationIssue]:
        """レジストリ全体の整合性チェック.

        チェック項目:
        - source_id の一意性
        - collection_method が collection_methods.json に存在するか
        - config_ref.file が実在するか
        - enabled=true かつ neo4j_connected=false のソースに警告

        Returns
        -------
        list[ValidationIssue]
            検出された問題のリスト。空リストなら問題なし。
        """
        issues: list[ValidationIssue] = []

        try:
            methods = self.load_collection_methods()
        except (FileNotFoundError, json.JSONDecodeError) as e:
            issues.append(
                ValidationIssue(
                    level="error",
                    message=f"Failed to load collection_methods.json: {e}",
                ),
            )
            return issues

        try:
            registry = self.load_source_registry()
        except (FileNotFoundError, json.JSONDecodeError) as e:
            issues.append(
                ValidationIssue(
                    level="error",
                    message=f"Failed to load source_registry.json: {e}",
                ),
            )
            return issues

        # source_id の一意性チェック
        seen_ids: set[str] = set()
        for source in registry.sources:
            if source.source_id in seen_ids:
                issues.append(
                    ValidationIssue(
                        level="error",
                        source_id=source.source_id,
                        message=f"Duplicate source_id: '{source.source_id}'",
                    ),
                )
            seen_ids.add(source.source_id)

        # collection_method の存在チェック
        for source in registry.sources:
            if not methods.has_method(source.collection_method):
                issues.append(
                    ValidationIssue(
                        level="error",
                        source_id=source.source_id,
                        message=(
                            f"Unknown collection_method: '{source.collection_method}'. "
                            f"Defined methods: {methods.method_ids()}"
                        ),
                    ),
                )

        # config_ref.file の実在チェック
        for source in registry.sources:
            if source.config_ref is None:
                continue
            ref_file = source.config_ref.file
            # scripts/ 内のPythonファイルも許可
            candidates = [
                self.config_dir / ref_file,
                self.config_dir.parent.parent / "scripts" / ref_file,
            ]
            if not any(c.exists() for c in candidates):
                issues.append(
                    ValidationIssue(
                        level="warning",
                        source_id=source.source_id,
                        message=f"Config file not found: '{ref_file}'",
                    ),
                )

        # enabled=true かつ neo4j_connected=false の警告
        for source in registry.sources:
            if source.enabled and not source.neo4j_connected:
                issues.append(
                    ValidationIssue(
                        level="warning",
                        source_id=source.source_id,
                        message="Source is enabled but not connected to Neo4j pipeline",
                    ),
                )

        return issues

    def summary(self) -> dict:
        """レジストリのサマリーを返す.

        Returns
        -------
        dict
            統計情報を含む辞書。
        """
        registry = self.load_source_registry()
        methods = self.load_collection_methods()

        by_method: dict[str, int] = {}
        by_instance: dict[str, int] = {}
        enabled_count = 0
        connected_count = 0

        for source in registry.sources:
            by_method[source.collection_method] = (
                by_method.get(source.collection_method, 0) + 1
            )
            by_instance[source.target_instance] = (
                by_instance.get(source.target_instance, 0) + 1
            )
            if source.enabled:
                enabled_count += 1
            if source.neo4j_connected:
                connected_count += 1

        return {
            "version": registry.version,
            "updated_at": registry.updated_at,
            "total_sources": len(registry.sources),
            "enabled": enabled_count,
            "disabled": len(registry.sources) - enabled_count,
            "neo4j_connected": connected_count,
            "neo4j_disconnected": len(registry.sources) - connected_count,
            "by_collection_method": by_method,
            "by_target_instance": by_instance,
            "defined_methods": methods.method_ids(),
        }
