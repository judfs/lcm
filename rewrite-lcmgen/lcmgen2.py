import dataclasses
from pathlib import Path
import sys
from typing import List, Optional, TextIO
import typing
import enum
from ctypes import c_int64, c_uint64

import lcm_tokenize
from lcm_tokenize import TokenType, Tokenize

# -----------------------------------------------------------------------------

KW_STRUCT = "struct"
KW_PACKAGE = "package"
KW_CONST = "const"

KW_ENUM = "enum"
"""Invalid keyword like `goto` in Java."""
# -----------------------------------------------------------------------------


GenOptions = typing.TypedDict(
    "GenOptions",
    {
        "package_prefix": str,
        "tokenize": bool,
    },
    total=False,
)


@dataclasses.dataclass
class LcmTypename:
    """
    Represents the name of a type, including package.
    """

    lctypename: str
    """fully-qualified name, e.g., "edu.mit.dgc.laser_t" """

    package: str
    """package name, e.g., "edu.mit.dgc" """

    shortname: str
    """e.g., "laser_t" """


class DimensionMode(enum.Enum):
    """
    Represents the size of a dimension of an array. The size can be either
    dynamic (a variable) or a constant.
    """

    # Mode of an array's dimension is part of a struct's hash
    # -> Changing these values would be a breaking change.
    # Values were defaulted in the C enum :(
    CONST = 0
    VAR = 1


@dataclasses.dataclass
class Dimension:
    mode: DimensionMode
    size: str
    """A string containing either a member variable name or a constant."""


@dataclasses.dataclass
class Member:
    """
    Represents one member of a struct, including (if its an array), its dimensions.
    """

    type: LcmTypename
    membername: str

    dimensions: List[Dimension]
    """An array of lcm_dimension_t. A scalar is a 1-dimensional array of length 1."""

    comment: Optional[str]
    """Comments in the LCM type definition immediately before a member declaration are attached to that member."""


@dataclasses.dataclass
class Constant:
    typename: str
    membername: str
    val_str: str
    comment: Optional[str]


@dataclasses.dataclass
class Struct:
    """
    A first-class LCM object declaration.
    """

    structname: LcmTypename

    members: List[Member]

    structs: "List[Struct]"
    constants: List[Constant]

    lcmfile: Path
    """file/path of function that declared it"""

    hash: int

    comment: Optional[str]
    """Comments in the LCM type definition immediately before a struct is declared are attached to that struct."""

    file_comment: Optional[str]
    """
    Comments in the LCM type definition before the package statement
    are placed at the top of the file after the "generated with lcm" statement.
    """


@dataclasses.dataclass
class ParseCache:
    package: str
    """Remembers the last-specified package name, which is prepended to other types."""

    comment_doc: Optional[str]
    """Last parsed comment, waiting to be attached to the next parsed thing."""

    file_comment: Optional[str]
    """Comment at the top of the LCM file. Waiting to be attached to a struct."""


@dataclasses.dataclass
class Lcmgen:
    """
    State used when parsing LCM declarations. The gopt is essentially a set of
    key-value pairs that configure various options. structs and enums are
    populated according to the parsed definitions.
    """

    parse_cache: ParseCache
    """State used while parsing. Shouldn't be used during code generation."""

    gopt: GenOptions

    structs: List[Struct]


# Will copy the c style for now
def create_lcmgen():
    return Lcmgen(
        parse_cache=ParseCache(
            package="",
            comment_doc=None,
            file_comment=None,
        ),
        structs=[],
        gopt={},
    )


def create_typename(lcmgen: Lcmgen, raw_typename: str):
    """
    Parse a type into package and class name.  If no package is
    specified, we will try to use the package from the last specified
    "package" directive, like in Java.
    """

    tmp = raw_typename
    typename = raw_typename
    # package name: everything before the last ".", or "" if there is no "."
    #
    # shortname: everything after the last ".", or everything if
    # there is no "."
    last_dot_loc = tmp.rfind(".")
    if last_dot_loc == -1:
        shortname = tmp
        if shortname in PRIMITIVE_TYPES:
            package = ""
        else:
            # We're overriding the package name using the last directive.
            package = lcmgen.parse_cache.package
            if package:
                typename = f"{package}.{shortname}"
            else:
                typename = shortname
    else:
        package = tmp[:last_dot_loc]
        shortname = tmp[last_dot_loc + 1 :]

    #
    package_prefix = lcmgen.gopt.get("package_prefix", "")
    if package_prefix and shortname not in PRIMITIVE_TYPES:

        package = f".{package}" if package else ""
        package = f"{package_prefix}{package}"

        typename = f"{package}.{shortname}"

    #
    return LcmTypename(
        lctypename=typename,
        package=package,
        shortname=shortname,
    )


def create_struct(lcmgen: Lcmgen, src_path: Path, structname: str):
    return Struct(
        comment=None,
        constants=[],
        file_comment=None,
        members=[],
        lcmfile=src_path,
        structs=[],
        structname=create_typename(lcmgen, structname),
        hash=0,
    )


# def create_constant(type:str, name:str, value:str):

# def create_member():
#     return Member()

# -----------------------------------------------------------------------------

PRIMITIVE_TYPES = [
    "int8_t",
    "int16_t",
    "int32_t",
    "int64_t",
    "byte",
    "float",
    "double",
    "string",
    "boolean",
]
"""
lcm's built-in types. Note that unsigned types are not present
because there is no safe java implementation. 
Really, 
  You don't want to add unsigned types.
"""


ARRAY_DIMENSION_TYPES = ["int8_t", "int16_t", "int32_t", "int64_t"]
"""Types that can be legally used as array dimensions."""

CONST_TYPES = ["int8_t", "int16_t", "int32_t", "int64_t", "float", "double"]
"""Types that can be legally used as const values"""

# Values from <stdint.h>
INT_TYPES = {
    "int8_t": ((-128), (127)),
    "int16_t": ((-32767 - 1), (32767)),
    "int32_t": ((-2147483647 - 1), (2147483647)),
    "int64_t": ((-9223372036854775807 - 1), (9223372036854775807)),
}


def int_in_type_bounds(val: int, type: str):
    bounds = INT_TYPES[type]
    return bounds[0] <= val <= bounds[1]


def is_legal_member_name(s: str):
    c = s[0]
    return c.isalpha() or c == "_"


def is_array_dimension_type(typename:LcmTypename):
    return typename.lctypename in ARRAY_DIMENSION_TYPES

# -----------------------------------------------------------------------------


# TODO make sure this is correct in python
def hash_update(v: int, char_ord: int) -> int:
    """
    Make the hash dependent on the value of the given character.
    The order that hash_update is called in IS important.
    """

    c = char_ord

    v = ((v << 8) ^ (v >> 55)) + c
    return c_int64(v).value


def hash_string_update(v: int, s: str) -> int:
    v = hash_update(v, len(s))

    for c in s:
        v = hash_update(v, ord(c))

    return v


def hash_structure(structure: Struct):
    # TODO SUPER verify this is ported correctly

    v = 0x12345678

    # NO: Purposefully, we do NOT include the structname in the hash.
    # this allows people to rename data types and still have them work.
    #
    # In contrast, we DO hash the types of a structs members (and their names).
    #  v = hash_string_update(v, lr->structname);

    for member in structure.members:

        # Hash the member name
        v = hash_string_update(v, member.membername)

        #  if the member is a primitive type, include the type
        #  signature in the hash. Do not include them for compound
        #  members, because their contents will be included, and we
        #  don't want a struct's name change to break the hash.
        if member.type.lctypename in PRIMITIVE_TYPES:
            v = hash_string_update(v, member.type.lctypename)

        # Hash the dimensionality information
        v = hash_update(v, len(member.dimensions))

        for dim in member.dimensions:
            v = hash_update(v, dim.mode.value)
            v = hash_string_update(v, dim.size)

    return v


# -----------------------------------------------------------------------------


def find_member(structure: Struct, name: str) -> Optional[Member]:
    # return next(filter(lambda it: it.membername == name, structure.members), None)
    for it in structure.members:
        if it.membername == name:
            return it
    return None


def find_const(structure: Struct, name: str) -> Optional[Constant]:
    for it in structure.constants:
        if it.membername == name:
            return it
    return None


# -----------------------------------------------------------------------------


def semantic_error(t: Tokenize, msg: str):
    """
    Semantic error: It parsed fine, but it's illegal. (we don't try to identify the offending token).
    NoReturn
    """

    print()
    print(msg)
    print(f"{t.path} : {t.token_line}")
    print(f"{t.buffer}")
    sys.exit(1)


def semantic_warning(t: Tokenize, msg: str):
    """Semantic warning: It parsed fine, but it's dangerous."""
    print()
    print(msg)
    print(f"{t.path} : {t.token_line}")
    print(f"{t.buffer}")


def parse_error(t: Tokenize, msg: str):
    """
    Parsing error: We cannot continue.
    NoReturn
    """
    print()
    print(msg)

    print(f"{t.path} : {t.token_line}")
    print(f"{t.buffer}")
    # Pad with tabs if the original text had tabs
    margin = "".join(
        map(lambda c: c if c.isspace() else " ", t.buffer[: t.token_column])
    )
    print(f"{margin}^")

    sys.exit(1)


def parse_try_consume_comment(
    lcmgen: Optional[Lcmgen], t: Tokenize, store_comment_doc: bool
):
    """
    Consume any available comments and store them in lcmgen->comment_doc
    Comments are allowed in most positions in the lcm grammar.
    However they are only significant in specific positions.
    Call with store_comment_doc=0 to discard any parsed comments.
    Call with store_comment_doc=1 to save the parsed comment to lcmgen->comment_doc.
      This discards the previous value of lcmgen->comment_doc.

    lcmgen MUST not be None if store_comment_doc is True
    """
    if store_comment_doc:
        assert lcmgen is not None
        lcmgen.parse_cache.comment_doc = None

    while lcm_tokenize.tokenize_peek(t) is not None and t.token_type == TokenType.COMMENT:
        lcm_tokenize.tokenize_next(t)

        if store_comment_doc:
            assert lcmgen is not None
            if lcmgen.parse_cache.comment_doc is None:
                lcmgen.parse_cache.comment_doc = t.token
            else:
                lcmgen.parse_cache.comment_doc = (
                    f"{lcmgen.parse_cache.comment_doc}\n{t.token}"
                )


def parse_try_consume(t: Tokenize, token: str):
    """If the next non-comment token is "tok", consume it and return True"""

    parse_try_consume_comment(None, t, False)
    res = lcm_tokenize.tokenize_peek(t)
    if  res is None:
        parse_error(t, f"End of file while looking for {token}.")

    get_next = t.token_type != TokenType.COMMENT and t.token == token
    if get_next:
        lcm_tokenize.tokenize_next(t)
    return get_next


def parse_require(t: Tokenize, token: str):
    """
    Consume the next token. If it's not "tok", an error is emitted and the program exits.
    """
    parse_try_consume_comment(None, t, False)

    res = lcm_tokenize.tokenize_next(t)
    while t.token_type == TokenType.COMMENT:
        res = lcm_tokenize.tokenize_next(t)

    if  res is None or t.token != token:
        parse_error(t, f"Expected token: {token}")


def tokenize_next_or_fail(t: Tokenize, description: str):
    """
    Require that the next token exist (not EOF).
    Description is a human-readable description of what was expected to be read.
    """
    res = lcm_tokenize.tokenize_next(t)
    if res is None:
        parse_error(t, f"End of file reached, expected: {description}.")


def parse_const(lcmgen: Lcmgen, structure: Struct, t: Tokenize) -> None:
    parse_try_consume_comment(lcmgen, t, False)
    tokenize_next_or_fail(t, "type identifier")

    # Get type
    if t.token not in CONST_TYPES:
        parse_error(t, f"Invalid type for const")
    typename = t.token

    def another_constant():
        # Get the name
        parse_try_consume_comment(lcmgen, t, False)

        tokenize_next_or_fail(t, "name identifier")
        membername = t.token
        if not is_legal_member_name(membername):
            parse_error(t, f"Invalid member name. Name must start with [a-zA-Z_].")

        # Make sure the name is new
        if (
            find_const(structure, membername) is not None
            or find_member(structure, membername) is not None
        ):
            semantic_error(t, f"Duplicate member name '{membername}")

        #  Get the value
        parse_require(t, "=")
        parse_try_consume_comment(lcmgen, t, False)
        tokenize_next_or_fail(t, "constant value")

        # Consume last parsed comment
        comment = None
        comment, lcmgen.parse_cache.comment_doc = (
            lcmgen.parse_cache.comment_doc,
            comment,
        )

        valstr = t.token
        if typename in INT_TYPES:
            try:
                intval = int(valstr, base=0)
            except ValueError:
                parse_error(t, "Expected integer value")

            if not int_in_type_bounds(intval, typename):
                semantic_error(t, f"Integer value out of bounds for {typename}.")

        elif typename in ["float", "double"]:
            try:
                fval = float(valstr)
            except ValueError:
                parse_error(t, "Expected floating point value")
            # TODO Determine a good metric for if a float literal is in range for f32 or f64
            # Comparing to max/min values isn't super relaxant.
        else:
            print(f"Unhandled / Invalid case: {typename}")
            assert False, "lcmgen "

        #
        const = Constant(
            typename=typename, membername=membername, comment=comment, val_str=valstr
        )
        structure.constants.append(const)

    # float a = 1.0
    another_constant()
    while parse_try_consume(t, ","):
        # , b = 2.0, c=3.0
        another_constant()

    parse_require(t, ";")


def parse_member(lcmgen: Lcmgen, structure: Struct, t: Tokenize) -> None:
    """Parse a member declaration."""
    # This looks long and scary, but most of the code is for semantic analysis (error checking)

    # Read a type specification.
    # Then read members (multiple members can be defined per-line.)
    # Each member can have different array dimensionalities.

    # Inline
    if parse_try_consume(t, KW_STRUCT):
        parse_error(t, "Recursive structs are not supported.")

    elif parse_try_consume(t, KW_ENUM):
        parse_error(t, "LCM enums are no longer supported.")

    elif parse_try_consume(t, KW_CONST):
        parse_const(lcmgen, structure, t)
        return

    #
    parse_try_consume_comment(lcmgen, t, False)
    tokenize_next_or_fail(t, "type identifier")

    if not is_legal_member_name(t.token):
        parse_error(t, "Invalid type name.")

    if t.token == "int":
        semantic_warning(
            t, "int type should probably be int8_t, int16_t, int32_t, or int64_t"
        )

    typename = create_typename(lcmgen, t.token)

    # "do _ while there are commas"
    while True:
        parse_try_consume_comment(lcmgen, t, False)
        tokenize_next_or_fail(t, "name identifier")

        membername = t.token
        if not is_legal_member_name(membername):
            parse_error(t, f"Invalid member name. Name must start with [a-zA-Z_].")

        # Make sure the name is new
        if (
            find_const(structure, membername) is not None
            or find_member(structure, membername) is not None
        ):
            semantic_error(t, f"Duplicate member name '{membername}")

        # Consume last parsed comment
        comment = None
        comment, lcmgen.parse_cache.comment_doc = (
            lcmgen.parse_cache.comment_doc,
            comment,
        )

        member = Member(
            type=typename,
            membername=membername,
            comment=comment,
            dimensions=[],
        )

        structure.members.append(member)

        while parse_try_consume(t, "["):
            parse_try_consume_comment(lcmgen, t, False)
            tokenize_next_or_fail(t, "array size")

            # Invalid close
            if t.token == "]":
                semantic_error(t, "Array size must be provided.")

            dim_mode: DimensionMode
            size: str

            # Constant literal
            size_arg = t.token
            if size_arg.isdigit():

                intval = int(size_arg)
                if intval <= 0:
                    semantic_error(t, "Constant array size must be > 0")
                dim_mode = DimensionMode.CONST
                size = size_arg
            else:

                if not is_legal_member_name(size_arg):
                    semantic_error(t, "Array size variable must have a valid name.")

                if dim_const := find_const(structure, size_arg):
                    if dim_const.typename not in CONST_TYPES:
                        semantic_error(
                            t, f"Array dimension '{size_arg}' must be an integer type."
                        )
                    dim_mode = DimensionMode.CONST
                    size = dim_const.val_str

                else:
                    dim_var = find_member(structure, size_arg)

                    if dim_var is None:
                        semantic_error(
                            t,
                            f"Unknown array size argument '{size_arg}'.\n"
                            f"Size arguments must be declared before the array.",
                        )
                    # Shouldn't be needed but the type checker is taking the day off
                    assert dim_var is not None

                    if len(dim_var.dimensions) != 0 or not is_array_dimension_type(dim_var.type) :
                        semantic_error(
                            t,
                            f"Array dimension '{size_arg}' must be a scalar integer type.",
                        )

                    dim_mode = DimensionMode.VAR
                    size = size_arg

            parse_require(t, "]")
            dim = Dimension(mode=dim_mode, size=size)
            member.dimensions.append(dim)
        # END while parse_try_consume(t, "[")

        if not parse_try_consume(t, ","):
            break
    # END while True
    parse_require(t, ";")
    # END parse_member


def parse_struct(lcmgen: Lcmgen, lcmfile: Path, t: Tokenize):

    # Assume the "struct" token is already consumed
    parse_try_consume_comment(lcmgen, t, False)
    tokenize_next_or_fail(t, "struct name")

    name = t.token

    structure = create_struct(lcmgen, lcmfile, name)

    # Consume available comments

    structure.file_comment, lcmgen.parse_cache.file_comment = (
        lcmgen.parse_cache.file_comment,
        structure.file_comment,
    )

    structure.comment, lcmgen.parse_cache.comment_doc = (
        lcmgen.parse_cache.comment_doc,
        structure.comment,
    )

    parse_require(t, "{")

    while True:
        # Save member comment
        parse_try_consume_comment(lcmgen, t, True)

        if parse_try_consume(t, "}"):
            break

        parse_member(lcmgen, structure, t)

    structure.hash = hash_structure(structure)

    return structure


def find_struct(lcmgen: Lcmgen, package: str, name: str) -> Optional[Struct]:
    for struct in lcmgen.structs:
        if struct.structname.package == package and struct.structname.shortname == name:
            return struct
    return None


def parse_entity(lcmgen: Lcmgen, lcmfile: Path, t: Tokenize) -> bool:
    # (top-level construct)

    parse_try_consume_comment(lcmgen, t, True)

    res = lcm_tokenize.tokenize_next(t)
    if res is None:
        return False

    if t.token == KW_PACKAGE:
        # Consume comment
        lcmgen.parse_cache.file_comment = lcmgen.parse_cache.comment_doc
        lcmgen.parse_cache.comment_doc = None

        parse_try_consume_comment(lcmgen, t, False)
        tokenize_next_or_fail(t, "package name")
        lcmgen.parse_cache.package = t.token
        parse_require(t, ";")
        return True

    if t.token == KW_STRUCT:
        structure = parse_struct(lcmgen, lcmfile, t)

        prev = find_struct(
            lcmgen, structure.structname.package, structure.structname.shortname
        )
        if prev is not None:
            print(
                f"ERROR: Duplicate type '{structure.structname.lctypename} declared in {lcmfile}. \n"
                f"       It was previously declared in {prev.lcmfile}."
            )
            return False
        lcmgen.structs.append(structure)
        return True

    if t.token == KW_ENUM:
        print("Enums are no longer supported.")
        return False

    parse_error(t, "Missing struct token.")
    return False


# -----------------------------------------------------------------------------


def handle_file(lcmgen: Lcmgen, path: Path) -> bool:

    t = lcm_tokenize.create(path)
    if t is None:
        print(f"Failed to open {path}.")
        return False

    if lcmgen.gopt.get("tokenize"):
        ntok = 0

        pad = 6
        print(f'{"tok#":{pad}} {"line":{pad}} {"col":{pad}}: token')
        while lcm_tokenize.tokenize_next(t) is not None:
            print(
                f"{ntok:{pad}} {t.token_line:{pad}} {t.token_column:{pad}}: {t.token}"
            )
            ntok += 1
        return True

    res = parse_entity(lcmgen, path, t)
    while res:
        res = parse_entity(lcmgen, path, t)

    t.f.close()
    # XXX The condition in the C code is a bit unclear
    return True


# -----------------------------------------------------------------------------

# There is no need to do it this way in python, but for the sake of comparing to the c implementation
# Just porting 1 to 1


def dump_typename(typename: LcmTypename):
    print(f"\t{typename.lctypename:20}", end="")


def dump_member(member: Member):
    dump_typename(member.type)

    print(f"  {member.membername}", end="")

    for dim in member.dimensions:
        if dim.mode == DimensionMode.CONST:
            print(f" [ (const) {dim.size} ]", end="")
        elif dim.mode == DimensionMode.VAR:
            print(f" [ (var) {dim.size} ]", end="")
        else:
            assert False
    print()


def dump_struct(struct: Struct):
    hash = c_uint64(struct.hash).value
    print(f"struct {struct.structname.lctypename} [hash={hash:#016x}]")
    # print(f"struct {struct.structname.lctypename} [hash={hash:#019x}]")
    for member in struct.members:
        dump_member(member)


def dump_lcmgen(lcmgen: Lcmgen):
    for struct in lcmgen.structs:
        dump_struct(struct)
