import pytest

from prismaa.parser.lexer import LexError, Token, TokenKind, tokenize


def kinds(source: str) -> list[TokenKind]:
    return [t.kind for t in tokenize(source) if t.kind != TokenKind.EOF]


def values(source: str) -> list[str]:
    return [t.value for t in tokenize(source) if t.kind != TokenKind.EOF]


# ---------------------------------------------------------------------------
# Basic tokens
# ---------------------------------------------------------------------------


def test_ident():
    toks = [t for t in tokenize("hello") if t.kind != TokenKind.EOF]
    assert toks == [Token(TokenKind.IDENT, "hello", 1)]


def test_string():
    toks = [t for t in tokenize('"hello world"') if t.kind != TokenKind.EOF]
    assert toks == [Token(TokenKind.STRING, '"hello world"', 1)]


def test_integer():
    toks = [t for t in tokenize("42") if t.kind != TokenKind.EOF]
    assert toks == [Token(TokenKind.NUMBER, "42", 1)]


def test_float():
    toks = [t for t in tokenize("3.14") if t.kind != TokenKind.EOF]
    assert toks == [Token(TokenKind.NUMBER, "3.14", 1)]


def test_double_at_before_at():
    assert kinds("@@unique") == [TokenKind.DOUBLE_AT, TokenKind.IDENT]
    assert kinds("@id") == [TokenKind.AT, TokenKind.IDENT]


def test_punctuation():
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
    assert kinds(source) == expected


# ---------------------------------------------------------------------------
# Whitespace and comments
# ---------------------------------------------------------------------------


def test_horizontal_whitespace_skipped():
    assert kinds("a   b") == [TokenKind.IDENT, TokenKind.IDENT]


def test_regular_comment_skipped():
    assert kinds("// this is a comment\nfoo") == [TokenKind.NEWLINE, TokenKind.IDENT]


def test_doc_comment_kept():
    toks = [t for t in tokenize("/// doc comment\n") if t.kind != TokenKind.EOF]
    assert toks[0].kind == TokenKind.DOC_COMMENT
    assert toks[0].value == "/// doc comment"


def test_newline_emitted():
    assert TokenKind.NEWLINE in kinds("a\nb")


def test_carriage_return_skipped():
    # Windows line endings should not produce extra tokens
    assert kinds("a\r\nb") == [TokenKind.IDENT, TokenKind.NEWLINE, TokenKind.IDENT]


# ---------------------------------------------------------------------------
# Line tracking
# ---------------------------------------------------------------------------


def test_line_numbers():
    toks = tokenize("a\nb\nc")
    ident_toks = [t for t in toks if t.kind == TokenKind.IDENT]
    assert [t.line for t in ident_toks] == [1, 2, 3]


def test_newline_token_line():
    toks = tokenize("a\nb")
    nl = next(t for t in toks if t.kind == TokenKind.NEWLINE)
    assert nl.line == 1


# ---------------------------------------------------------------------------
# String edge cases
# ---------------------------------------------------------------------------


def test_string_with_escape():
    toks = [t for t in tokenize(r'"say \"hi\""') if t.kind != TokenKind.EOF]
    assert toks[0].kind == TokenKind.STRING


def test_empty_string():
    toks = [t for t in tokenize('""') if t.kind != TokenKind.EOF]
    assert toks[0] == Token(TokenKind.STRING, '""', 1)


# ---------------------------------------------------------------------------
# EOF
# ---------------------------------------------------------------------------


def test_eof_always_last():
    toks = tokenize("")
    assert toks[-1].kind == TokenKind.EOF


def test_eof_on_empty():
    assert tokenize("") == [Token(TokenKind.EOF, "", 1)]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_unexpected_character_raises():
    with pytest.raises(LexError, match="Unexpected character"):
        tokenize("model Foo { id Int $ }")


# ---------------------------------------------------------------------------
# Realistic snippets
# ---------------------------------------------------------------------------


def test_field_with_attributes():
    source = "id Int @id @default(autoincrement())"
    k = kinds(source)
    assert k == [
        TokenKind.IDENT,  # id
        TokenKind.IDENT,  # Int
        TokenKind.AT,
        TokenKind.IDENT,  # id
        TokenKind.AT,
        TokenKind.IDENT,  # default
        TokenKind.LPAREN,
        TokenKind.IDENT,  # autoincrement
        TokenKind.LPAREN,
        TokenKind.RPAREN,
        TokenKind.RPAREN,
    ]


def test_relation_attribute():
    source = "@relation(fields: [companyId], references: [id])"
    k = kinds(source)
    assert TokenKind.COLON in k
    assert TokenKind.LBRACKET in k


def test_block_attribute_unique():
    source = '@@unique([cik, accessionNumber])'
    k = kinds(source)
    assert k[0] == TokenKind.DOUBLE_AT
    assert k[1] == TokenKind.IDENT


def test_optional_field_type():
    source = "valueInt Int?"
    k = kinds(source)
    assert k == [TokenKind.IDENT, TokenKind.IDENT, TokenKind.QUESTION]


def test_list_field_type():
    source = "filings Filing[]"
    k = kinds(source)
    assert k == [TokenKind.IDENT, TokenKind.IDENT, TokenKind.LBRACKET, TokenKind.RBRACKET]


def test_unsupported_type():
    source = 'value Unsupported("any")?'
    k = kinds(source)
    assert k == [
        TokenKind.IDENT,  # value
        TokenKind.IDENT,  # Unsupported
        TokenKind.LPAREN,
        TokenKind.STRING,  # "any"
        TokenKind.RPAREN,
        TokenKind.QUESTION,
    ]
