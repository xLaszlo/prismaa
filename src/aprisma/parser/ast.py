from __future__ import annotations

from dataclasses import dataclass, field

_PRISMA_SCALARS = frozenset({"String", "Boolean", "Int", "BigInt", "Float", "Decimal", "DateTime", "Json", "Bytes"})


@dataclass
class FunctionCall:
    """Represents a zero-argument function call in an attribute, e.g. autoincrement(), now()."""

    name: str

    def __repr__(self) -> str:
        return f"{self.name}()"


# Valid types for attribute argument values.
AttributeValue = str | int | float | bool | list[str] | FunctionCall


@dataclass
class AttributeArg:
    """A single argument inside an attribute's parentheses."""

    name: str | None  # None for positional arguments
    value: AttributeValue


@dataclass
class Attribute:
    """A field-level (@) or block-level (@@) attribute."""

    name: str  # without leading @ or @@
    args: list[AttributeArg] = field(default_factory=list)

    def arg(self, name: str) -> AttributeValue | None:
        """Return the value of a named argument, or None if absent."""
        for a in self.args:
            if a.name == name:
                return a.value
        return None

    def first_positional(self) -> AttributeValue | None:
        """Return the first positional argument value, or None."""
        for a in self.args:
            if a.name is None:
                return a.value
        return None


@dataclass
class Field:
    name: str
    type: str  # e.g. "String", "Int", "Company", "Unsupported"
    is_list: bool
    is_optional: bool
    # For Unsupported("native_type") fields, holds the native type string.
    native_type: str | None = None
    attributes: list[Attribute] = field(default_factory=list)
    doc_comment: str | None = None

    @property
    def is_unsupported(self) -> bool:
        return self.type == "Unsupported"

    @property
    def is_relation(self) -> bool:
        if any(a.name == "relation" for a in self.attributes):
            return True
        return self.type not in _PRISMA_SCALARS and self.type != "Unsupported"

    @property
    def column_name(self) -> str:
        """Actual DB column name, respecting @map."""
        for attr in self.attributes:
            if attr.name == "map":
                v = attr.first_positional()
                if isinstance(v, str):
                    return v
        return self.name

    def has_attr(self, name: str) -> bool:
        return any(a.name == name for a in self.attributes)

    def get_attr(self, name: str) -> Attribute | None:
        for a in self.attributes:
            if a.name == name:
                return a
        return None


@dataclass
class Model:
    name: str
    fields: list[Field] = field(default_factory=list)
    block_attributes: list[Attribute] = field(default_factory=list)
    doc_comment: str | None = None

    @property
    def is_ignored(self) -> bool:
        return any(a.name == "ignore" for a in self.block_attributes)

    @property
    def table_name(self) -> str:
        """Actual DB table name, respecting @@map."""
        for attr in self.block_attributes:
            if attr.name == "map":
                v = attr.first_positional()
                if isinstance(v, str):
                    return v
        return self.name

    def scalar_fields(self) -> list[Field]:
        """Non-relation, non-unsupported fields."""
        return [f for f in self.fields if not f.is_relation and not f.is_unsupported]

    def relation_fields(self) -> list[Field]:
        return [f for f in self.fields if f.is_relation]


@dataclass
class Generator:
    name: str
    properties: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: str = "") -> str:
        return self.properties.get(key, default)


@dataclass
class Datasource:
    name: str
    provider: str


@dataclass
class Schema:
    datasource: Datasource | None = None
    generators: list[Generator] = field(default_factory=list)
    models: list[Model] = field(default_factory=list)

    @property
    def generator(self) -> Generator | None:
        """The first generator block, or None."""
        return self.generators[0] if self.generators else None

    def active_models(self) -> list[Model]:
        """Models that are not marked @@ignore."""
        return [m for m in self.models if not m.is_ignored]
