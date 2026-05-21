from __future__ import annotations

from .ast import (
    Attribute,
    AttributeArg,
    AttributeValue,
    Datasource,
    Field,
    FunctionCall,
    Generator,
    Model,
    Schema,
)
from .lexer import Token, TokenKind, tokenize


class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    # ------------------------------------------------------------------
    # Token stream primitives
    # ------------------------------------------------------------------

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if tok.kind != TokenKind.EOF:
            self._pos += 1
        return tok

    def _at(self, kind: TokenKind) -> bool:
        return self._peek().kind == kind

    def _expect(self, kind: TokenKind) -> Token:
        tok = self._peek()
        if tok.kind != kind:
            raise ParseError(f"Expected {kind.name} but got {tok.kind.name} ({tok.value!r}) at line {tok.line}")
        return self._advance()

    def _skip_newlines(self) -> None:
        while self._at(TokenKind.NEWLINE):
            self._advance()

    def _at_end_of_statement(self) -> bool:
        return self._at(TokenKind.NEWLINE) or self._at(TokenKind.RBRACE) or self._at(TokenKind.EOF)

    # ------------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------------

    def parse(self) -> Schema:
        schema = Schema()
        pending_doc: str | None = None

        while not self._at(TokenKind.EOF):
            if self._at(TokenKind.NEWLINE):
                self._advance()
                continue

            if self._at(TokenKind.DOC_COMMENT):
                # Accumulate consecutive doc comment lines.
                lines = []
                while self._at(TokenKind.DOC_COMMENT):
                    lines.append(self._advance().value[3:].strip())
                    self._skip_newlines()
                pending_doc = "\n".join(lines)
                continue

            if not self._at(TokenKind.IDENT):
                self._advance()
                continue

            keyword = self._peek().value
            if keyword == "generator":
                schema.generators.append(self._parse_generator())
            elif keyword == "datasource":
                schema.datasource = self._parse_datasource()
            elif keyword == "model":
                model = self._parse_model()
                model.doc_comment = pending_doc
                schema.models.append(model)
            else:
                # Unknown top-level block (e.g. "enum", "type") — skip entirely.
                self._skip_block()

            pending_doc = None

        return schema

    # ------------------------------------------------------------------
    # Blocks
    # ------------------------------------------------------------------

    def _parse_generator(self) -> Generator:
        self._expect(TokenKind.IDENT)  # consume "generator"
        name = self._expect(TokenKind.IDENT).value
        self._skip_newlines()
        self._expect(TokenKind.LBRACE)
        props: dict[str, str] = {}
        while not self._at(TokenKind.RBRACE) and not self._at(TokenKind.EOF):
            self._skip_newlines()
            if self._at(TokenKind.RBRACE):
                break
            key = self._expect(TokenKind.IDENT).value
            self._expect(TokenKind.EQUALS)
            value = self._parse_scalar_value()
            props[key] = str(value)
            self._skip_newlines()
        self._expect(TokenKind.RBRACE)
        return Generator(name=name, properties=props)

    def _parse_datasource(self) -> Datasource:
        self._expect(TokenKind.IDENT)  # consume "datasource"
        name = self._expect(TokenKind.IDENT).value
        self._skip_newlines()
        self._expect(TokenKind.LBRACE)
        provider = "unknown"
        while not self._at(TokenKind.RBRACE) and not self._at(TokenKind.EOF):
            self._skip_newlines()
            if self._at(TokenKind.RBRACE):
                break
            key = self._expect(TokenKind.IDENT).value
            self._expect(TokenKind.EQUALS)
            value = self._parse_scalar_value()
            if key == "provider":
                provider = str(value)
            self._skip_newlines()
        self._expect(TokenKind.RBRACE)
        return Datasource(name=name, provider=provider)

    def _parse_model(self) -> Model:
        self._expect(TokenKind.IDENT)  # consume "model"
        name = self._expect(TokenKind.IDENT).value
        self._skip_newlines()
        self._expect(TokenKind.LBRACE)
        self._skip_newlines()

        fields: list[Field] = []
        block_attrs: list[Attribute] = []
        pending_doc: str | None = None

        while not self._at(TokenKind.RBRACE) and not self._at(TokenKind.EOF):
            if self._at(TokenKind.NEWLINE):
                self._advance()
                continue

            if self._at(TokenKind.DOC_COMMENT):
                lines = []
                while self._at(TokenKind.DOC_COMMENT):
                    lines.append(self._advance().value[3:].strip())
                    self._skip_newlines()
                pending_doc = "\n".join(lines)
                continue

            if self._at(TokenKind.DOUBLE_AT):
                block_attrs.append(self._parse_block_attribute())
                pending_doc = None
                continue

            if self._at(TokenKind.IDENT):
                f = self._parse_field()
                f.doc_comment = pending_doc
                fields.append(f)
                pending_doc = None
                continue

            # Unexpected token inside model block — skip to next newline.
            self._advance()

        self._expect(TokenKind.RBRACE)
        return Model(name=name, fields=fields, block_attributes=block_attrs)

    def _skip_block(self) -> None:
        """Skip an unknown top-level block (keyword name { ... })."""
        self._advance()  # keyword
        if self._at(TokenKind.IDENT):
            self._advance()  # name
        self._skip_newlines()
        if not self._at(TokenKind.LBRACE):
            return
        self._advance()  # {
        depth = 1
        while depth > 0 and not self._at(TokenKind.EOF):
            tok = self._advance()
            if tok.kind == TokenKind.LBRACE:
                depth += 1
            elif tok.kind == TokenKind.RBRACE:
                depth -= 1

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    def _parse_field(self) -> Field:
        name = self._expect(TokenKind.IDENT).value
        type_name, native_type, is_list, is_optional = self._parse_field_type()
        attributes: list[Attribute] = []
        while self._at(TokenKind.AT) and not self._at_end_of_statement():
            attributes.append(self._parse_field_attribute())
        # Consume the trailing newline (or leave RBRACE for the caller).
        if self._at(TokenKind.NEWLINE):
            self._advance()
        return Field(
            name=name,
            type=type_name,
            is_list=is_list,
            is_optional=is_optional,
            native_type=native_type,
            attributes=attributes,
        )

    def _parse_field_type(self) -> tuple[str, str | None, bool, bool]:
        """Return (type_name, native_type, is_list, is_optional)."""
        type_name = self._expect(TokenKind.IDENT).value
        native_type: str | None = None

        # Handle Unsupported("native_type")
        if type_name == "Unsupported" and self._at(TokenKind.LPAREN):
            self._advance()
            native_type = self._expect(TokenKind.STRING).value.strip('"')
            self._expect(TokenKind.RPAREN)

        is_list = False
        is_optional = False

        if self._at(TokenKind.LBRACKET):
            self._advance()
            self._expect(TokenKind.RBRACKET)
            is_list = True
        elif self._at(TokenKind.QUESTION):
            self._advance()
            is_optional = True

        return type_name, native_type, is_list, is_optional

    # ------------------------------------------------------------------
    # Attributes
    # ------------------------------------------------------------------

    def _parse_field_attribute(self) -> Attribute:
        """Parse a @name or @name(...) field attribute."""
        self._expect(TokenKind.AT)
        name = self._expect(TokenKind.IDENT).value
        args = self._parse_attribute_args() if self._at(TokenKind.LPAREN) else []
        return Attribute(name=name, args=args)

    def _parse_block_attribute(self) -> Attribute:
        """Parse a @@name or @@name(...) block attribute."""
        self._expect(TokenKind.DOUBLE_AT)
        name = self._expect(TokenKind.IDENT).value
        args = self._parse_attribute_args() if self._at(TokenKind.LPAREN) else []
        if self._at(TokenKind.NEWLINE):
            self._advance()
        return Attribute(name=name, args=args)

    def _parse_attribute_args(self) -> list[AttributeArg]:
        self._expect(TokenKind.LPAREN)
        args: list[AttributeArg] = []
        while not self._at(TokenKind.RPAREN) and not self._at(TokenKind.EOF):
            args.append(self._parse_attribute_arg())
            if self._at(TokenKind.COMMA):
                self._advance()
        self._expect(TokenKind.RPAREN)
        return args

    def _parse_attribute_arg(self) -> AttributeArg:
        """Parse one argument: either `name: value` or a bare `value`."""
        # Named argument: IDENT COLON value
        if self._at(TokenKind.IDENT) and self._tokens[self._pos + 1].kind == TokenKind.COLON:
            name = self._advance().value
            self._advance()  # consume ':'
            value = self._parse_attr_value()
            return AttributeArg(name=name, value=value)
        # Positional argument
        return AttributeArg(name=None, value=self._parse_attr_value())

    def _parse_attr_value(self) -> AttributeValue:
        tok = self._peek()

        if tok.kind == TokenKind.STRING:
            self._advance()
            return tok.value[1:-1]  # strip surrounding quotes

        if tok.kind == TokenKind.NUMBER:
            self._advance()
            return float(tok.value) if "." in tok.value else int(tok.value)

        if tok.kind == TokenKind.LBRACKET:
            return self._parse_array()

        if tok.kind == TokenKind.IDENT:
            name = self._advance().value
            if name == "true":
                return True
            if name == "false":
                return False
            # Function call: name()
            if self._at(TokenKind.LPAREN):
                self._advance()
                self._expect(TokenKind.RPAREN)
                return FunctionCall(name)
            # Bare identifier (e.g. enum value, env("VAR") key)
            return name

        raise ParseError(f"Unexpected token in attribute value: {tok!r}")

    def _parse_array(self) -> list[str]:
        """Parse [ident, ident, ...] — used in @@unique, @relation fields/references."""
        self._expect(TokenKind.LBRACKET)
        items: list[str] = []
        while not self._at(TokenKind.RBRACKET) and not self._at(TokenKind.EOF):
            items.append(self._expect(TokenKind.IDENT).value)
            if self._at(TokenKind.COMMA):
                self._advance()
        self._expect(TokenKind.RBRACKET)
        return items

    # ------------------------------------------------------------------
    # Shared value parsing (generator / datasource properties)
    # ------------------------------------------------------------------

    def _parse_scalar_value(self) -> AttributeValue:
        """Parse a simple key = value pair value (string, number, bool, or env(...))."""
        tok = self._peek()
        if tok.kind == TokenKind.STRING:
            self._advance()
            return tok.value[1:-1]
        if tok.kind == TokenKind.NUMBER:
            self._advance()
            return float(tok.value) if "." in tok.value else int(tok.value)
        if tok.kind == TokenKind.IDENT:
            name = self._advance().value
            if name == "true":
                return True
            if name == "false":
                return False
            # env("VAR") — return the raw identifier; resolution happens at runtime
            if self._at(TokenKind.LPAREN):
                self._advance()
                inner = self._peek()
                value = inner.value[1:-1] if inner.kind == TokenKind.STRING else inner.value
                self._advance()
                self._expect(TokenKind.RPAREN)
                return value
            return name
        if tok.kind == TokenKind.LBRACKET:
            return self._parse_array()
        raise ParseError(f"Unexpected token in value: {tok!r}")


def parse(source: str) -> Schema:
    """Parse a Prisma schema string and return a :class:`Schema` AST."""
    tokens = tokenize(source)
    return Parser(tokens).parse()
