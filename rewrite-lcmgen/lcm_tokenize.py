# `tokenize` is a module on the path.

import dataclasses
from pathlib import Path
from typing import Optional, TextIO
import typing
import enum

# -----------------------------------------------------------------------------


class TokenType(enum.Enum):
    INVALID = enum.auto()
    EOF = enum.auto()
    COMMENT = enum.auto()
    OTHER = enum.auto()


@dataclasses.dataclass
class Tokenize:
    token: str  # A buffer type might be better, but for now str will do

    token_line: int
    token_column: int

    current_char: str
    current_line: int
    current_column: int

    # If there is an ungetc() pending, unget_char >0 and contains the
    # char. unget_line and unget_column are the line and column of
    # the unget'd char.
    unget_char: Optional[str]
    unget_line: int
    unget_column: int

    buffer: str
    buffer_line: int
    buffer_column: int
    buffer_len: int

    path: Path
    f: TextIO

    hasnext: int  # bool?

    token_type: TokenType


def create(path: Path) -> Optional[Tokenize]:

    try:
        f = path.open("r")
    except:
        return None

    return Tokenize(
        f=f,
        path=path,
        #
        token="",
        token_line=-1,
        token_column=-1,
        #
        buffer="",
        buffer_column=0,
        buffer_len=0,
        buffer_line=0,
        #
        hasnext=0,
        #
        current_char="",
        current_column=0,
        current_line=0,
        #
        unget_char=None,
        unget_column=0,
        unget_line=0,
        #
        token_type=TokenType.INVALID,
    )



def next_char(t: Tokenize) -> Optional[str]:
    if t.unget_char:
        t.current_char = t.unget_char
        t.current_line = t.unget_line
        t.current_column = t.unget_column

        t.unget_char = None
        return t.current_char

    #
    if t.buffer_column == t.buffer_len:
        t.buffer = t.f.readline()
        if not t.buffer:
            return None
        t.buffer_len = len(t.buffer)
        t.buffer_line += 1
        t.buffer_column = 0

    #
    t.current_char = t.buffer[t.buffer_column]
    t.current_line = t.buffer_line
    t.current_column = t.buffer_column

    t.buffer_column += 1

    return t.current_char


def unget(t: Tokenize):
    t.unget_char = t.current_char
    t.unget_line = t.current_line
    t.unget_column = t.current_column


def flush_line(t: Tokenize):
    """Read until at the end of the current line."""
    c = next_char(t)
    while c and c != "\n":
        c = next_char(t)
    # Done


def add_char_to_token(t: Tokenize, c: str):
    t.token += c


def tokenize_extended_comment(t: Tokenize) -> Optional[int]:
    pos = 0
    t.token = ""

    # So far, the tokenizer has processed "/*"
    comment_finished = False

    while not comment_finished:
        pos_line_start = pos

        # Go through leading whitespace.
        c: Optional[str]
        while True:
            c = next_char(t)
            if c and (c == " " or c == "\t"):
                add_char_to_token(t, c)
                pos += 1
            else:
                break

        # Go through asterisks
        got_asterisk = False
        while c == "*":
            add_char_to_token(t, c)
            pos += 1
            got_asterisk = True
            c = next_char(t)

        # Strip out leading comment characters in the line.
        if got_asterisk:
            pos = pos_line_start
            t.token = t.token[:pos_line_start]
            if c == "/":
                comment_finished = True
                break
            elif c == " ":
                # If a space immediately followed the leading asterisks,
                # then skip it.
                c = next_char(t)

        # The rest of the line is comment content.
        while not comment_finished and c and c != "\n":
            last_c = c

            add_char_to_token(t, c)
            pos += 1
            c = next_char(t)

            if last_c == "*" and c == "/":
                comment_finished = True
                pos -= 1

        #
        if not comment_finished:
            if not c:
                print(f"{t.path} : EOF reached while parsing comment!")
                return None

            assert c == "\n"
            if pos_line_start != pos:
                add_char_to_token(t, c)
                pos += 1

    # END while not comment_finished:
    # t->token[pos] = 0;
    t.token_type = TokenType.COMMENT

    return pos


@typing.overload
def unescape(c: None) -> None: ...
@typing.overload
def unescape(c: str) -> str: ...
def unescape(c: Optional[str]):
    if c is None:
        return None

    if c == "n":
        return "\n"
    elif c == "r":
        return "\r"
    elif c == "t":
        return "\t"

    return c


# List because None in "" is not valid but None in [] is.
OPERATOR_CHARS = list("!~<>=&|^%*+=") 

# no '.' so that name spaces are one token
SINGLE_CHAR_TOKENS = list("();\",:'[]")


def tokenize_next_internal(t: Tokenize):
    t.token_type = TokenType.INVALID
    pos = 0
    t.token = ""

    c = next_char(t)
    # Find non whitespace
    while c and c.isspace():
        c = next_char(t)
    if not c:
        t.token_type = TokenType.INVALID
        return None

    # A token is starting. mark its position.
    t.token_line = t.current_line
    t.token_column = t.current_column

    # c is a character literal?
    if c == "'":
        t.token += c
        pos += 1
        c = next_char(t)
        if c == "\\":
            c = unescape(next_char(t))
        if not c:
            return None

        t.token += c
        pos += 1

        c = next_char(t)
        if c != "'":
            return None
        t.token += c
        pos += 1
        t.token_type = TokenType.OTHER
        return pos

    # c is a string literal?
    if c == '"':

        t.token += c
        pos += 1

        escape_next = False

        # Keep reading until close quote
        # XXX Suspect
        while True:
            c = next_char(t)
            if c is None:
                return None

            if escape_next:
                escape_next = False
                c = unescape(c)
                # t.token += c
                # pos +=1
                continue

            if c == '"':
                t.token += c
                pos += 1

                # XXX Should be?
                # t.token_type = TokenType.OTHER
                return pos

            if c == "\\":
                escape_next = True
                continue

            t.token += c
            pos += 1

    # c is an operator?
    if c in OPERATOR_CHARS:
        t.token_type = TokenType.OTHER
        while c in OPERATOR_CHARS:
            t.token += c
            pos += 1
            c = next_char(t)
        unget(t)
        return pos

    # c is a comment?
    if c == "/":
        t.token += c
        pos += 1

        c = next_char(t)
        if not c:
            # Not invalid??
            t.token_type = TokenType.OTHER
            return pos

        if c == "*":
            return tokenize_extended_comment(t)

        if c == "/":
            t.token_type = TokenType.COMMENT

            c = next_char(t)
            # Strip out leading '/' characters
            while c == "/":
                c = next_char(t)
            # Strip out leading whitespace.
            while c and c == ' ':
                c = next_char(t)

            pos = 0
            t.token = ""
            while c and c != "\n":
                t.token += c
                pos += 1
                c = next_char(t)

            unget(t)
            return pos

        # If the '/' is not followed by a '*' or a '/', then treat it like an operator
        t.token_type = TokenType.OTHER
        unget(t)
        return pos

    # ELSE: All tokens are alpha-numeric blobs

    # XXX Was a do while. did it need to be?
    t.token_type = TokenType.OTHER
    while c and not c.isspace():
        t.token += c
        pos += 1

        if c in SINGLE_CHAR_TOKENS:
            return pos

        c = next_char(t)
        if c in SINGLE_CHAR_TOKENS or c in OPERATOR_CHARS:
            unget(t)
            return pos

    return pos

    # END tokenize_next_internal


def tokenize_next(t: Tokenize):

    if t.hasnext:
        t.hasnext = 0
        return 0

    return tokenize_next_internal(t)


def tokenize_peek(t: Tokenize):
    if t.hasnext:
        return 0
    res = tokenize_next(t)
    if res is not None:
        t.hasnext = 1
    return res
