from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import Table


@dataclass
class RelationMeta:
    name: str
    model: str
    fk_fields: list[str]
    references: list[str]
    is_list: bool


@dataclass
class ModelMetadata:
    table: Table
    model_cls: type
    field_column_map: dict[str, str]
    relations: list[RelationMeta] = field(default_factory=list)
    unique_fields: list[str] = field(default_factory=list)
    updated_at_fields: list[str] = field(default_factory=list)
