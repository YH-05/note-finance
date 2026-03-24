"""Source registry: データソースと収集方法の一元管理."""

from data_pipeline.registry.loader import RegistryLoader
from data_pipeline.registry.models import (
    CollectionMethodDef,
    CollectionMethodRegistry,
    ConfigRef,
    DataSource,
    SourceRegistry,
    ValidationIssue,
)

__all__ = [
    "CollectionMethodDef",
    "CollectionMethodRegistry",
    "ConfigRef",
    "DataSource",
    "RegistryLoader",
    "SourceRegistry",
    "ValidationIssue",
]
