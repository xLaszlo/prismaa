from pathlib import Path

import pytest

from prismaa.parser import parse
from prismaa.parser.ast import FunctionCall

EXAMPLE_SCHEMA = (Path(__file__).parent.parent.parent / "example" / "schema.prisma").read_text()


# ---------------------------------------------------------------------------
# Generator block
# ---------------------------------------------------------------------------


def test_generator_name():
    schema = parse('generator client { provider = "prismaa" }')
    assert schema.generator is not None
    assert schema.generator.name == "client"


def test_generator_properties():
    src = """
    generator client {
      provider  = "prismaa"
      interface = "asyncio"
      output    = "../prisma"
    }
    """
    g = parse(src).generator
    assert g.get("provider") == "prismaa"
    assert g.get("interface") == "asyncio"
    assert g.get("output") == "../prisma"


# ---------------------------------------------------------------------------
# Datasource block
# ---------------------------------------------------------------------------


def test_datasource_provider():
    src = 'datasource db { provider = "sqlite" }'
    ds = parse(src).datasource
    assert ds is not None
    assert ds.name == "db"
    assert ds.provider == "sqlite"


# ---------------------------------------------------------------------------
# Model discovery
# ---------------------------------------------------------------------------


def test_model_names():
    schema = parse(EXAMPLE_SCHEMA)
    names = [m.name for m in schema.models]
    for expected in ("User", "Profile", "Post", "Category", "Tag", "PostTag", "Comment", "Asset"):
        assert expected in names


def test_active_models_excludes_ignored():
    schema = parse(EXAMPLE_SCHEMA)
    active = [m.name for m in schema.active_models()]
    assert "FtsIndex" not in active
    assert "User" in active


# ---------------------------------------------------------------------------
# Field types
# ---------------------------------------------------------------------------


def test_scalar_field():
    src = "model M { name String }"
    fields = parse(src).models[0].fields
    assert fields[0].name == "name"
    assert fields[0].type == "String"
    assert not fields[0].is_list
    assert not fields[0].is_optional


def test_optional_field():
    src = "model M { value Int? }"
    f = parse(src).models[0].fields[0]
    assert f.is_optional
    assert not f.is_list


def test_list_field():
    src = "model M { posts Post[] }"
    f = parse(src).models[0].fields[0]
    assert f.is_list
    assert not f.is_optional


def test_unsupported_field():
    src = 'model M { value Unsupported("any")? }'
    f = parse(src).models[0].fields[0]
    assert f.is_unsupported
    assert f.native_type == "any"
    assert f.is_optional


def test_all_scalar_types():
    src = """
    model M {
      a  String
      b  Int
      c  Float
      d  Boolean
      e  DateTime
      f  Json
      g  Bytes
      h  BigInt
      i  Decimal
    }
    """
    fields = {f.name: f.type for f in parse(src).models[0].fields}
    assert fields == {
        "a": "String",
        "b": "Int",
        "c": "Float",
        "d": "Boolean",
        "e": "DateTime",
        "f": "Json",
        "g": "Bytes",
        "h": "BigInt",
        "i": "Decimal",
    }


# ---------------------------------------------------------------------------
# Field attributes
# ---------------------------------------------------------------------------


def test_id_attribute():
    src = "model M { id Int @id }"
    f = parse(src).models[0].fields[0]
    assert f.has_attr("id")


def test_unique_attribute():
    src = "model M { email String @unique }"
    f = parse(src).models[0].fields[0]
    assert f.has_attr("unique")


def test_default_autoincrement():
    src = "model M { id Int @id @default(autoincrement()) }"
    f = parse(src).models[0].fields[0]
    default_attr = f.get_attr("default")
    assert default_attr is not None
    val = default_attr.first_positional()
    assert isinstance(val, FunctionCall)
    assert val.name == "autoincrement"


def test_default_now():
    src = "model M { createdAt DateTime @default(now()) }"
    f = parse(src).models[0].fields[0]
    val = f.get_attr("default").first_positional()
    assert isinstance(val, FunctionCall)
    assert val.name == "now"


def test_default_string():
    src = 'model M { status String @default("active") }'
    f = parse(src).models[0].fields[0]
    val = f.get_attr("default").first_positional()
    assert val == "active"


def test_default_bool():
    src = "model M { active Boolean @default(true) }"
    f = parse(src).models[0].fields[0]
    val = f.get_attr("default").first_positional()
    assert val is True


def test_default_int():
    src = "model M { count Int @default(0) }"
    f = parse(src).models[0].fields[0]
    val = f.get_attr("default").first_positional()
    assert val == 0


def test_map_attribute():
    src = 'model M { camelCase String @map("snake_case") }'
    f = parse(src).models[0].fields[0]
    assert f.column_name == "snake_case"


def test_updated_at_attribute():
    src = "model M { updatedAt DateTime @updatedAt }"
    f = parse(src).models[0].fields[0]
    assert f.has_attr("updatedAt")


def test_relation_named_args():
    src = "model M { company Company @relation(fields: [companyId], references: [id]) }"
    f = parse(src).models[0].fields[0]
    rel = f.get_attr("relation")
    assert rel is not None
    assert rel.arg("fields") == ["companyId"]
    assert rel.arg("references") == ["id"]


def test_relation_field_detected():
    src = "model M { company Company @relation(fields: [companyId], references: [id]) }"
    f = parse(src).models[0].fields[0]
    assert f.is_relation


# ---------------------------------------------------------------------------
# Block attributes
# ---------------------------------------------------------------------------


def test_block_unique():
    src = "model M { id Int\n @@unique([cik, accessionNumber]) }"
    model = parse(src).models[0]
    attr = next(a for a in model.block_attributes if a.name == "unique")
    assert attr.first_positional() == ["cik", "accessionNumber"]


def test_block_map():
    src = 'model M { id Int\n @@map("_actual_table") }'
    model = parse(src).models[0]
    assert model.table_name == "_actual_table"


def test_block_ignore():
    src = "model M { id Int\n @@ignore }"
    model = parse(src).models[0]
    assert model.is_ignored


def test_block_id():
    src = "model M { a String\n b String\n @@id([a, b]) }"
    model = parse(src).models[0]
    attr = next(a for a in model.block_attributes if a.name == "id")
    assert attr.first_positional() == ["a", "b"]


# ---------------------------------------------------------------------------
# Doc comments
# ---------------------------------------------------------------------------


def test_model_doc_comment():
    src = """
/// A company in the system.
model Company {
  id Int @id
}
"""
    model = parse(src).models[0]
    assert model.doc_comment == "A company in the system."


def test_field_doc_comment():
    src = """
model M {
  /// Primary key.
  id Int @id
}
"""
    f = parse(src).models[0].fields[0]
    assert f.doc_comment == "Primary key."


def test_multiline_doc_comment():
    src = """
/// Line one.
/// Line two.
model M { id Int @id }
"""
    model = parse(src).models[0]
    assert model.doc_comment == "Line one.\nLine two."


# ---------------------------------------------------------------------------
# Model helpers
# ---------------------------------------------------------------------------


def test_scalar_fields_excludes_relations():
    src = """
    model Filing {
      id        Int     @id
      company   Company @relation(fields: [companyId], references: [id])
      companyId Int
    }
    """
    model = parse(src).models[0]
    scalar_names = [f.name for f in model.scalar_fields()]
    assert "company" not in scalar_names
    assert "id" in scalar_names
    assert "companyId" in scalar_names


def test_relation_fields():
    src = """
    model Filing {
      id        Int     @id
      company   Company @relation(fields: [companyId], references: [id])
    }
    """
    model = parse(src).models[0]
    assert [f.name for f in model.relation_fields()] == ["company"]


# ---------------------------------------------------------------------------
# Full example schema round-trip
# ---------------------------------------------------------------------------


def test_example_schema_parses_without_error():
    schema = parse(EXAMPLE_SCHEMA)
    assert schema.datasource is not None
    assert schema.generator is not None
    assert len(schema.models) > 0


def test_example_schema_user_fields():
    schema = parse(EXAMPLE_SCHEMA)
    user = next(m for m in schema.models if m.name == "User")
    field_names = [f.name for f in user.fields]
    assert "id" in field_names
    assert "email" in field_names
    assert "createdAt" in field_names
    assert "updatedAt" in field_names
    assert "posts" in field_names
    assert "profile" in field_names


def test_example_schema_comment_block_unique():
    schema = parse(EXAMPLE_SCHEMA)
    comment = next(m for m in schema.models if m.name == "Comment")
    unique_attrs = [a for a in comment.block_attributes if a.name == "unique"]
    assert len(unique_attrs) == 1
    assert unique_attrs[0].first_positional() == ["postId", "authorId"]


def test_example_schema_post_optional_fields():
    schema = parse(EXAMPLE_SCHEMA)
    post = next(m for m in schema.models if m.name == "Post")
    optional_names = [f.name for f in post.fields if f.is_optional]
    assert "rating" in optional_names
    assert "publishedAt" in optional_names
    assert "categoryId" in optional_names


def test_example_schema_asset_bytes_field():
    schema = parse(EXAMPLE_SCHEMA)
    asset = next(m for m in schema.models if m.name == "Asset")
    data = next(f for f in asset.fields if f.name == "data")
    assert data.type == "Bytes"


def test_example_schema_post_tag_composite_id():
    schema = parse(EXAMPLE_SCHEMA)
    post_tag = next(m for m in schema.models if m.name == "PostTag")
    id_attr = next(a for a in post_tag.block_attributes if a.name == "id")
    assert id_attr.first_positional() == ["postId", "tagId"]
    assert post_tag.table_name == "post_tags"


def test_example_schema_fts_index_ignored():
    schema = parse(EXAMPLE_SCHEMA)
    fts = next(m for m in schema.models if m.name == "FtsIndex")
    assert fts.is_ignored
    assert fts.table_name == "_fts_index"


def test_example_schema_fts_index_unsupported_field():
    schema = parse(EXAMPLE_SCHEMA)
    fts = next(m for m in schema.models if m.name == "FtsIndex")
    term = next(f for f in fts.fields if f.name == "term")
    assert term.is_unsupported
    assert term.native_type == "any"
    assert term.is_optional


def test_example_schema_all_relation_types():
    """Verify 1-1, 1-n, and many-to-many are all present."""
    schema = parse(EXAMPLE_SCHEMA)
    models = {m.name: m for m in schema.models}

    # 1-1: User → Profile
    profile_field = next(f for f in models["User"].fields if f.name == "profile")
    assert profile_field.is_optional  # optional because Profile may not exist yet

    # 1-n: User → Post[]
    posts_field = next(f for f in models["User"].fields if f.name == "posts")
    assert posts_field.is_list

    # many-to-many via PostTag
    tags_field = next(f for f in models["Post"].fields if f.name == "tags")
    assert tags_field.is_list
    assert tags_field.type == "PostTag"


def test_example_schema_profile_map():
    schema = parse(EXAMPLE_SCHEMA)
    profile = next(m for m in schema.models if m.name == "Profile")
    assert profile.table_name == "user_profiles"


def test_example_schema_post_index():
    schema = parse(EXAMPLE_SCHEMA)
    post = next(m for m in schema.models if m.name == "Post")
    index_attr = next(a for a in post.block_attributes if a.name == "index")
    assert index_attr.first_positional() == ["authorId", "createdAt"]


def test_example_schema_scalar_type_coverage():
    """All nine Prisma scalar types appear somewhere in the active models."""
    schema = parse(EXAMPLE_SCHEMA)
    all_types = {f.type for m in schema.active_models() for f in m.scalar_fields()}
    for scalar in ("String", "Int", "Float", "Boolean", "DateTime", "Json", "Bytes", "BigInt", "Decimal"):
        assert scalar in all_types, f"{scalar} not found in any active model"
