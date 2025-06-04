import argparse
from pathlib import Path
import sys

# ---

import lcmgen2

# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------

program_description = """
"""

program_example = """
"""


def main():
    parser = argparse.ArgumentParser(
        description=program_description,
        epilog=program_example,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    #
    parser.add_argument("input_files",nargs="+")


    #
    debug_group = parser.add_argument_group("Diagnostic")
    debug_group.add_argument(
        "-t",
        "--tokenize",
        action="store_true",
        help="Show tokenization",
    )
    debug_group.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Show parsed file",
    )

    # -------------------------------------------------------------------------

    args = parser.parse_args()
    dargs = vars(args)
    print(dargs)

    gen = lcmgen2.create_lcmgen()
    gen.gopt = dargs  # type: ignore

    for path in args.input_files:
        suc = lcmgen2.handle_file(gen, Path(path))
        if not suc:
            sys.exit(1)

    if dargs["tokenize"]:
        sys.exit(0)

    if dargs["debug"]:
        lcmgen2.dump_lcmgen(gen)

    # END main


if __name__ == "__main__":
    main()
