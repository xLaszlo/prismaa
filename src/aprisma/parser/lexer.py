from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto


class TokenKind(Enum):
    IDENT = auto()
    STRING = auto()
    NUMBER = auto()
    DOUBLE_AT = auto()
    AT = auto()
    LBRACE = auto()
    RBRACE = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COLON = auto()
    COMMA = auto()
    EQUALS = auto()
    QUESTION = auto()
    DOC_COMMENT = auto()
    NEWLINE = auto()
    EOF = auto()


@dataclass
class Token:
    kind: TokenKind
    value: str
    line: int

    def __repr__(self) -> str:
        return f"Token({self.kind.name}, {self.value!r}, line={self.line})"


class LexError(Exception):
    pass


# Rules are tested in order; first match wins.
# None means "skip this token" (whitespace, regular comments).
_RULES: list[tuple[TokenKind | None, str]] = [
    (TokenKind.DOC_COMMENT, r"///[^\n]*"),
    (None, r"//[^\n]*"),  # regular comment — discard
    (None, r"[ \t]+"),  # horizontal whitespace — discard
    (TokenKind.NEWLINE, r"\n"),
    (TokenKind.STRING, r'"[^"\\]*(?:\\.[^"\\]*)*"'),
    (TokenKind.NUMBER, r"\d+\.\d+|\d+"),
    (TokenKind.DOUBLE_AT, r"@@"),  # must precede AT
    (TokenKind.AT, r"@"),
    (TokenKind.LBRACE, r"\{"),
    (TokenKind.RBRACE, r"\}"),
    (TokenKind.LPAREN, r"\("),
    (TokenKind.RPAREN, r"\)"),
    (TokenKind.LBRACKET, r"\["),
    (TokenKind.RBRACKET, r"\]"),
    (TokenKind.COLON, r":"),
    (TokenKind.COMMA, r","),
    (TokenKind.EQUALS, r"="),
    (TokenKind.QUESTION, r"\?"),
    (TokenKind.IDENT, r"[A-Za-z_][A-Za-z0-9_]*"),
    (None, r"\r"),  # bare carriage return — discard
]

_MASTER = re.compile(
    "|".join(f"(?P<r{i}>{pattern})" for i, (_, pattern) in enumerate(_RULES)),
)


def tokenize(source: str) -> list[Token]:
    """Lex *source* into a flat token list ending with an EOF token."""
    tokens: list[Token] = []
    line = 1

    for m in _MASTER.finditer(source):
        group_index = int(m.lastgroup[1:])  # "r7" → 7
        kind, _ = _RULES[group_index]
        value = m.group()

        if value == "\n":
            tokens.append(Token(TokenKind.NEWLINE, value, line))
            line += 1
        elif kind is not None:
            tokens.append(Token(kind, value, line))
        # kind is None → skip (whitespace / comments)

    # Verify the entire source was consumed (no unexpected characters).
    matched_len = sum(len(m.group()) for m in _MASTER.finditer(source))
    if matched_len != len(source):
        # Find the first unmatched character to give a useful error.
        pos = 0
        for m in _MASTER.finditer(source):
            if m.start() != pos:
                break
            pos = m.end()
        ctx = source[pos : pos + 20].replace("\n", "\\n")
        raise LexError(f"Unexpected character at line {line}: {ctx!r}")

    tokens.append(Token(TokenKind.EOF, "", line))
    return tokens
