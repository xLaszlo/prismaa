import unittest
from pathlib import Path

from prismaa.parser import parse
from prismaa.parser.ast import FunctionCall

EXAMPLE_SCHEMA = (Path(__file__).parent.parent.parent / "example" / "schema.prisma").read_text()


class TestGeneratorBlock(unittest.TestCase):
    def test_name(self):
        schema = parse('generator client { provider = "prismaa" }')
        self.assertIsNotNone(schema.generator)
        self.assertEqual(schema.generator.name, "client")

    def test_properties(self):
        src = """
        generator client {
          provider  = "prismaa"
          interface = "asyncio"
          output    = "../prisma"
        }
        """
        g = parse(src).generator
        self.assertEqual(g.get("provider"), "prismaa")
        self.assertEqual(g.get("interface"), "asyncio")
        self.assertEqual(g.get("output"), "../prisma")


class TestDatasourceBlock(unittest.TestCase):
    def test_provider(self):
        ds = parse('datasource db { provider = "sqlite" }').datasource
        self.assertIsNotNone(ds)
        self.assertEqual(ds.name, "db")
        self.assertEqual(ds.provider, "sqlite")


class TestModelDiscovery(unittest.TestCase):
    def test_model_names(self):
        names = [m.name for m in parse(EXAMPLE_SCHEMA).models]
        for expected in ("User", "Profile", "Post", "Category", "Tag", "PostTag", "Comment", "Asset"):
            self.assertIn(expected, names)

    def test_active_models_excludes_ignored(self):
        active = [m.name for m in parse(EXAMPLE_SCHEMA).active_models()]
        self.assertNotIn("FtsIndex", active)
        self.assertIn("User", active)


class TestFieldTypes(unittest.TestCase):
    def test_scalar_field(self):
        f = parse("model M { name String }").models[0].fields[0]
        self.assertEqual(f.name, "name")
        self.assertEqual(f.type, "String")
        self.assertFalse(f.is_list)
        self.assertFalse(f.is_optional)

    def test_optional_field(self):
        f = parse("model M { value Int? }").models[0].fields[0]
        self.assertTrue(f.is_optional)
        self.assertFalse(f.is_list)

    def test_list_field(self):
        f = parse("model M { posts Post[] }").models[0].fields[0]
        self.assertTrue(f.is_list)
        self.assertFalse(f.is_optional)

    def test_unsupported_field(self):
        f = parse('model M { value Unsupported("any")? }').models[0].fields[0]
        self.assertTrue(f.is_unsupported)
        self.assertEqual(f.native_type, "any")
        self.assertTrue(f.is_optional)

    def test_all_scalar_types(self):
        src = """
        model M {
          a String
          b Int
          c Float
          d Boolean
          e DateTime
          f Json
          g Bytes
          h BigInt
          i Decimal
        }
        """
        fields = {f.name: f.type for f in parse(src).models[0].fields}
        self.assertEqual(
            fields,
            {
                "a": "String",
                "b": "Int",
                "c": "Float",
                "d": "Boolean",
                "e": "DateTime",
                "f": "Json",
                "g": "Bytes",
                "h": "BigInt",
                "i": "Decimal",
            },
        )


class TestFieldAttributes(unittest.TestCase):
    def test_id_attribute(self):
        f = parse("model M { id Int @id }").models[0].fields[0]
        self.assertTrue(f.has_attr("id"))

    def test_unique_attribute(self):
        f = parse("model M { email String @unique }").models[0].fields[0]
        self.assertTrue(f.has_attr("unique"))

    def test_default_autoincrement(self):
        f = parse("model M { id Int @id @default(autoincrement()) }").models[0].fields[0]
        val = f.get_attr("default").first_positional()
        self.assertIsInstance(val, FunctionCall)
        self.assertEqual(val.name, "autoincrement")

    def test_default_now(self):
        f = parse("model M { createdAt DateTime @default(now()) }").models[0].fields[0]
        val = f.get_attr("default").first_positional()
        self.assertIsInstance(val, FunctionCall)
        self.assertEqual(val.name, "now")

    def test_default_string(self):
        f = parse('model M { status String @default("active") }').models[0].fields[0]
        self.assertEqual(f.get_attr("default").first_positional(), "active")

    def test_default_bool(self):
        f = parse("model M { active Boolean @default(true) }").models[0].fields[0]
        self.assertIs(f.get_attr("default").first_positional(), True)

    def test_default_int(self):
        f = parse("model M { count Int @default(0) }").models[0].fields[0]
        self.assertEqual(f.get_attr("default").first_positional(), 0)

    def test_map_attribute(self):
        f = parse('model M { camelCase String @map("snake_case") }').models[0].fields[0]
        self.assertEqual(f.column_name, "snake_case")

    def test_updated_at_attribute(self):
        f = parse("model M { updatedAt DateTime @updatedAt }").models[0].fields[0]
        self.assertTrue(f.has_attr("updatedAt"))

    def test_relation_named_args(self):
        src = "model M { company Company @relation(fields: [companyId], references: [id]) }"
        rel = parse(src).models[0].fields[0].get_attr("relation")
        self.assertIsNotNone(rel)
        self.assertEqual(rel.arg("fields"), ["companyId"])
        self.assertEqual(rel.arg("references"), ["id"])

    def test_relation_field_detected(self):
        src = "model M { company Company @relation(fields: [companyId], references: [id]) }"
        self.assertTrue(parse(src).models[0].fields[0].is_relation)


class TestBlockAttributes(unittest.TestCase):
    def test_block_unique(self):
        model = parse("model M { id Int\n @@unique([cik, accessionNumber]) }").models[0]
        attr = next(a for a in model.block_attributes if a.name == "unique")
        self.assertEqual(attr.first_positional(), ["cik", "accessionNumber"])

    def test_block_map(self):
        model = parse('model M { id Int\n @@map("_actual_table") }').models[0]
        self.assertEqual(model.table_name, "_actual_table")

    def test_block_ignore(self):
        model = parse("model M { id Int\n @@ignore }").models[0]
        self.assertTrue(model.is_ignored)

    def test_block_id(self):
        model = parse("model M { a String\n b String\n @@id([a, b]) }").models[0]
        attr = next(a for a in model.block_attributes if a.name == "id")
        self.assertEqual(attr.first_positional(), ["a", "b"])


class TestDocComments(unittest.TestCase):
    def test_model_doc_comment(self):
        src = "/// A company in the system.\nmodel Company {\n  id Int @id\n}"
        self.assertEqual(parse(src).models[0].doc_comment, "A company in the system.")

    def test_field_doc_comment(self):
        src = "model M {\n  /// Primary key.\n  id Int @id\n}"
        self.assertEqual(parse(src).models[0].fields[0].doc_comment, "Primary key.")

    def test_multiline_doc_comment(self):
        src = "/// Line one.\n/// Line two.\nmodel M { id Int @id }"
        self.assertEqual(parse(src).models[0].doc_comment, "Line one.\nLine two.")


class TestModelHelpers(unittest.TestCase):
    def test_scalar_fields_excludes_relations(self):
        src = """
        model Filing {
          id        Int     @id
          company   Company @relation(fields: [companyId], references: [id])
          companyId Int
        }
        """
        scalar_names = [f.name for f in parse(src).models[0].scalar_fields()]
        self.assertNotIn("company", scalar_names)
        self.assertIn("id", scalar_names)
        self.assertIn("companyId", scalar_names)

    def test_relation_fields(self):
        src = """
        model Filing {
          id      Int     @id
          company Company @relation(fields: [companyId], references: [id])
        }
        """
        self.assertEqual([f.name for f in parse(src).models[0].relation_fields()], ["company"])


class TestExampleSchema(unittest.TestCase):
    def setUp(self):
        self.schema = parse(EXAMPLE_SCHEMA)
        self.models = {m.name: m for m in self.schema.models}

    def test_parses_without_error(self):
        self.assertIsNotNone(self.schema.datasource)
        self.assertIsNotNone(self.schema.generator)
        self.assertGreater(len(self.schema.models), 0)

    def test_user_fields(self):
        field_names = [f.name for f in self.models["User"].fields]
        for name in ("id", "email", "createdAt", "updatedAt", "posts", "profile"):
            self.assertIn(name, field_names)

    def test_comment_block_unique(self):
        unique_attrs = [a for a in self.models["Comment"].block_attributes if a.name == "unique"]
        self.assertEqual(len(unique_attrs), 1)
        self.assertEqual(unique_attrs[0].first_positional(), ["postId", "authorId"])

    def test_post_optional_fields(self):
        optional_names = [f.name for f in self.models["Post"].fields if f.is_optional]
        self.assertIn("rating", optional_names)
        self.assertIn("publishedAt", optional_names)
        self.assertIn("categoryId", optional_names)

    def test_asset_bytes_field(self):
        data = next(f for f in self.models["Asset"].fields if f.name == "data")
        self.assertEqual(data.type, "Bytes")

    def test_post_tag_composite_id(self):
        id_attr = next(a for a in self.models["PostTag"].block_attributes if a.name == "id")
        self.assertEqual(id_attr.first_positional(), ["postId", "tagId"])
        self.assertEqual(self.models["PostTag"].table_name, "post_tags")

    def test_fts_index_ignored(self):
        fts = self.models["FtsIndex"]
        self.assertTrue(fts.is_ignored)
        self.assertEqual(fts.table_name, "_fts_index")

    def test_fts_index_unsupported_field(self):
        term = next(f for f in self.models["FtsIndex"].fields if f.name == "term")
        self.assertTrue(term.is_unsupported)
        self.assertEqual(term.native_type, "any")
        self.assertTrue(term.is_optional)

    def test_all_relation_types(self):
        profile_field = next(f for f in self.models["User"].fields if f.name == "profile")
        self.assertTrue(profile_field.is_optional)

        posts_field = next(f for f in self.models["User"].fields if f.name == "posts")
        self.assertTrue(posts_field.is_list)

        tags_field = next(f for f in self.models["Post"].fields if f.name == "tags")
        self.assertTrue(tags_field.is_list)
        self.assertEqual(tags_field.type, "PostTag")

    def test_profile_map(self):
        self.assertEqual(self.models["Profile"].table_name, "user_profiles")

    def test_post_index(self):
        index_attr = next(a for a in self.models["Post"].block_attributes if a.name == "index")
        self.assertEqual(index_attr.first_positional(), ["authorId", "createdAt"])

    def test_scalar_type_coverage(self):
        all_types = {f.type for m in self.schema.active_models() for f in m.scalar_fields()}
        for scalar in ("String", "Int", "Float", "Boolean", "DateTime", "Json", "Bytes", "BigInt", "Decimal"):
            self.assertIn(scalar, all_types)

    def test_active_models_excludes_ignored(self):
        active = [m.name for m in self.schema.active_models()]
        self.assertNotIn("FtsIndex", active)
        self.assertIn("User", active)
