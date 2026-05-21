from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from aprisma.parser.ast import Attribute, Field, Model, Schema

_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Prisma scalar type → SQLAlchemy column type
_SA_TYPE_MAP = {
    "String": "Text",
    "Int": "Integer",
    "Float": "Float",
    "Boolean": "Boolean",
    "DateTime": "DateTime",
    "Bytes": "LargeBinary",
    "BigInt": "BigInteger",
    "Decimal": "Numeric",
    "Json": "JSON",
}

# Prisma scalar type → Python type annotation
_PY_TYPE_MAP = {
    "String": "str",
    "Int": "int",
    "Float": "float",
    "Boolean": "bool",
    "DateTime": "datetime.datetime",
    "Bytes": "bytes",
    "BigInt": "int",
    "Decimal": "Decimal",
    "Json": "Any",
}

# Prisma scalar type → filter class name
_FILTER_TYPE_MAP = {
    "String": "StringFilter",
    "Int": "IntFilter",
    "Float": "FloatFilter",
    "Boolean": "BoolFilter",
    "DateTime": "DateTimeFilter",
    "Bytes": "BytesFilter",
    "BigInt": "BigIntFilter",
    "Decimal": "DecimalFilter",
}


def _sa_type(type_name: str) -> str:
    return _SA_TYPE_MAP.get(type_name, "Text")


def _py_type(type_name: str) -> str:
    return _PY_TYPE_MAP.get(type_name, "Any")


def _filter_type(type_name: str) -> str:
    return _FILTER_TYPE_MAP.get(type_name, "Any")


def _model_attr(model_name: str) -> str:
    """Convert model name to snake_case delegate attribute name."""
    return model_name[0].lower() + model_name[1:]


def _selectattr_no_default(fields: list[Field]) -> list[Field]:
    """Fields that have no default and are not optional (truly required on create)."""
    return [
        f
        for f in fields
        if not f.is_optional
        and not f.has_attr("default")
        and not f.has_attr("updatedAt")
        and not (f.has_attr("id") and f.has_attr("default"))
    ]


def _selectattr_has_default(fields: list[Field]) -> list[Field]:
    return [f for f in fields if f.is_optional or f.has_attr("default") or f.has_attr("updatedAt")]


def _selectattr_name(attrs: list[Attribute], name: str) -> list[Attribute]:
    return [a for a in attrs if a.name == name]


def _resolve_col_names(field_names: list[str], model: Model) -> list[str]:
    """Map Prisma field names to their actual DB column names (respecting @map)."""
    field_map = {f.name: f.column_name for f in model.fields}
    return [field_map.get(fn, fn) for fn in field_names]


def _lower(s: Any) -> str:
    if isinstance(s, bool):
        return "true" if s else "false"
    return str(s).lower()


def _tojson(value: Any) -> str:
    return json.dumps(value)


def _bool_lower(value: bool) -> str:
    return "True" if value else "False"


def _make_env(schema: Schema | None = None) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["sa_type"] = _sa_type
    env.filters["py_type"] = _py_type
    env.filters["filter_type"] = _filter_type
    env.filters["model_attr"] = _model_attr
    env.filters["selectattr_no_default"] = _selectattr_no_default
    env.filters["selectattr_has_default"] = _selectattr_has_default
    env.filters["selectattr_name"] = _selectattr_name
    env.filters["resolve_col_names"] = _resolve_col_names
    env.filters["lower"] = _lower
    env.filters["tojson"] = _tojson
    env.filters["bool_lower"] = _bool_lower

    _model_map: dict[str, Model] = {m.name: m for m in schema.models} if schema else {}

    def _resolve_col_names_for(field_names: list[str], model_name: str) -> list[str]:
        m = _model_map.get(model_name)
        if m is None:
            return field_names
        return _resolve_col_names(field_names, m)

    def _get_fk_target(field: Field, model: Model) -> tuple[str, str] | None:
        """Return (table_name, col_name) if this scalar field is an FK, else None."""
        for rel_field in model.relation_fields():
            rel_attr = rel_field.get_attr("relation")
            if rel_attr is None:
                continue
            fk_field_names: list[str] = rel_attr.arg("fields") or []  # type: ignore[assignment]
            refs: list[str] = rel_attr.arg("references") or []  # type: ignore[assignment]
            if field.name in fk_field_names:
                idx = fk_field_names.index(field.name)
                ref_field_name = refs[idx] if idx < len(refs) else None
                if ref_field_name:
                    related_model = _model_map.get(rel_field.type)
                    if related_model:
                        field_map = {f.name: f.column_name for f in related_model.fields}
                        ref_col = field_map.get(ref_field_name, ref_field_name)
                        return (related_model.table_name, ref_col)
        return None

    env.filters["resolve_col_names_for"] = _resolve_col_names_for
    env.filters["get_fk_target"] = _get_fk_target
    env.globals["true"] = True
    env.globals["false"] = False
    return env


_TEMPLATES = [
    ("tables.py.j2", "tables.py"),
    ("models.py.j2", "models.py"),
    ("types.py.j2", "types.py"),
    ("client.py.j2", "client.py"),
    ("__init__.py.j2", "__init__.py"),
]


def generate(schema: Schema, output_dir: Path) -> list[Path]:
    """Render all templates for *schema* into *output_dir*. Returns list of written paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    env = _make_env(schema)
    written: list[Path] = []
    ctx = {"schema": schema}
    for template_name, output_name in _TEMPLATES:
        tmpl = env.get_template(template_name)
        rendered = tmpl.render(**ctx)
        out_path = output_dir / output_name
        out_path.write_text(rendered, encoding="utf-8")
        written.append(out_path)

    return written
