import unittest

from aprisma.parser.lexer import LexError, Token, TokenKind, tokenize


def kinds(source: str) -> list[TokenKind]:
    return [t.kind for t in tokenize(source) if t.kind != TokenKind.EOF]


class TestBasicTokens(unittest.TestCase):
    def test_ident(self):
        toks = [t for t in tokenize("hello") if t.kind != TokenKind.EOF]
        self.assertEqual(toks, [Token(TokenKind.IDENT, "hello", 1)])

    def test_string(self):
        toks = [t for t in tokenize('"hello world"') if t.kind != TokenKind.EOF]
        self.assertEqual(toks, [Token(TokenKind.STRING, '"hello world"', 1)])

    def test_integer(self):
        toks = [t for t in tokenize("42") if t.kind != TokenKind.EOF]
        self.assertEqual(toks, [Token(TokenKind.NUMBER, "42", 1)])

    def test_float(self):
        toks = [t for t in tokenize("3.14") if t.kind != TokenKind.EOF]
        self.assertEqual(toks, [Token(TokenKind.NUMBER, "3.14", 1)])

    def test_double_at_before_at(self):
        self.assertEqual(kinds("@@unique"), [TokenKind.DOUBLE_AT, TokenKind.IDENT])
        self.assertEqual(kinds("@id"), [TokenKind.AT, TokenKind.IDENT])

    def test_punctuation(self):
        source = "{ } ( ) [ ] : , = ?"
        expected = [
            TokenKind.LBRACE,
            TokenKind.RBRACE,
            TokenKind.LPAREN,
            TokenKind.RPAREN,
            TokenKind.LBRACKET,
            TokenKind.RBRACKET,
            TokenKind.COLON,
            TokenKind.COMMA,
            TokenKind.EQUALS,
            TokenKind.QUESTION,
        ]
        self.assertEqual(kinds(source), expected)


class TestWhitespaceAndComments(unittest.TestCase):
    def test_horizontal_whitespace_skipped(self):
        self.assertEqual(kinds("a   b"), [TokenKind.IDENT, TokenKind.IDENT])

    def test_regular_comment_skipped(self):
        self.assertEqual(kinds("// this is a comment\nfoo"), [TokenKind.NEWLINE, TokenKind.IDENT])

    def test_doc_comment_kept(self):
        toks = [t for t in tokenize("/// doc comment\n") if t.kind != TokenKind.EOF]
        self.assertEqual(toks[0].kind, TokenKind.DOC_COMMENT)
        self.assertEqual(toks[0].value, "/// doc comment")

    def test_newline_emitted(self):
        self.assertIn(TokenKind.NEWLINE, kinds("a\nb"))

    def test_carriage_return_skipped(self):
        self.assertEqual(kinds("a\r\nb"), [TokenKind.IDENT, TokenKind.NEWLINE, TokenKind.IDENT])


class TestLineNumbers(unittest.TestCase):
    def test_ident_line_numbers(self):
        toks = tokenize("a\nb\nc")
        ident_toks = [t for t in toks if t.kind == TokenKind.IDENT]
        self.assertEqual([t.line for t in ident_toks], [1, 2, 3])

    def test_newline_token_line(self):
        toks = tokenize("a\nb")
        nl = next(t for t in toks if t.kind == TokenKind.NEWLINE)
        self.assertEqual(nl.line, 1)


class TestStringTokens(unittest.TestCase):
    def test_string_with_escape(self):
        toks = [t for t in tokenize(r'"say \"hi\""') if t.kind != TokenKind.EOF]
        self.assertEqual(toks[0].kind, TokenKind.STRING)

    def test_empty_string(self):
        toks = [t for t in tokenize('""') if t.kind != TokenKind.EOF]
        self.assertEqual(toks[0], Token(TokenKind.STRING, '""', 1))


class TestEOF(unittest.TestCase):
    def test_eof_always_last(self):
        self.assertEqual(tokenize("")[-1].kind, TokenKind.EOF)

    def test_eof_on_empty(self):
        self.assertEqual(tokenize(""), [Token(TokenKind.EOF, "", 1)])


class TestErrors(unittest.TestCase):
    def test_unexpected_character_raises(self):
        with self.assertRaises(LexError):
            tokenize("model Foo { id Int $ }")


class TestRealisticSnippets(unittest.TestCase):
    def test_field_with_attributes(self):
        source = "id Int @id @default(autoincrement())"
        self.assertEqual(
            kinds(source),
            [
                TokenKind.IDENT,
                TokenKind.IDENT,
                TokenKind.AT,
                TokenKind.IDENT,
                TokenKind.AT,
                TokenKind.IDENT,
                TokenKind.LPAREN,
                TokenKind.IDENT,
                TokenKind.LPAREN,
                TokenKind.RPAREN,
                TokenKind.RPAREN,
            ],
        )

    def test_relation_attribute(self):
        source = "@relation(fields: [companyId], references: [id])"
        self.assertIn(TokenKind.COLON, kinds(source))
        self.assertIn(TokenKind.LBRACKET, kinds(source))

    def test_block_attribute_unique(self):
        source = "@@unique([cik, accessionNumber])"
        k = kinds(source)
        self.assertEqual(k[0], TokenKind.DOUBLE_AT)
        self.assertEqual(k[1], TokenKind.IDENT)

    def test_optional_field_type(self):
        self.assertEqual(kinds("valueInt Int?"), [TokenKind.IDENT, TokenKind.IDENT, TokenKind.QUESTION])

    def test_list_field_type(self):
        self.assertEqual(
            kinds("filings Filing[]"),
            [TokenKind.IDENT, TokenKind.IDENT, TokenKind.LBRACKET, TokenKind.RBRACKET],
        )

    def test_unsupported_type(self):
        source = 'value Unsupported("any")?'
        self.assertEqual(
            kinds(source),
            [
                TokenKind.IDENT,
                TokenKind.IDENT,
                TokenKind.LPAREN,
                TokenKind.STRING,
                TokenKind.RPAREN,
                TokenKind.QUESTION,
            ],
        )
