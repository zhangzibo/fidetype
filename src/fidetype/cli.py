"""The ``fidetype`` command line (M7-01): one entry point, one subcommand per tool.

::

    fidetype validate stream.jsonl --level trust-ready   # conformance check of stream files
    fidetype trust --config trust.json stream.jsonl      # streaming trust layer -> trust_decision JSON Lines
    fidetype demo                                        # offline demo (synthetic streams)
    fidetype conformance ...                             # full conformance suite (check, consumer, vectors, ...)
    fidetype lsl run|replay-to-lsl|list ...              # Lab Streaming Layer input (needs the [lsl] extra)
    fidetype benchmark tracks|prepare|score|...          # open benchmark v0.1
    fidetype ledger verify|report ...                    # provenance ledger tools
    fidetype version

Each subcommand runs the same code as its ``python -m`` module, which
still works: ``python -m fidetype.conformance``,
``python -m fidetype.trust.streaming``, ``python -m fidetype.adapters.lsl``,
``python -m fidetype.benchmark``, ``python -m fidetype.trust.provenance``
and ``python -m fidetype.demo``.
"""

from __future__ import annotations

import sys
from typing import Callable, Sequence


def _validate(argv: list[str]) -> int:
    from fidetype.conformance.__main__ import main

    return main(["check", *argv])


def _conformance(argv: list[str]) -> int:
    from fidetype.conformance.__main__ import main

    return main(argv)


def _trust(argv: list[str]) -> int:
    from fidetype.trust.streaming import main

    return main(["replay", *argv])


def _lsl(argv: list[str]) -> int:
    from fidetype.adapters.lsl import main

    return main(argv)


def _benchmark(argv: list[str]) -> int:
    from fidetype.benchmark.__main__ import main

    return main(argv)


def _ledger(argv: list[str]) -> int:
    from fidetype.trust.provenance import main

    return main(argv)


def _demo(argv: list[str]) -> int:
    from fidetype.demo.__main__ import main

    return main(argv)


def _version(argv: list[str]) -> int:
    from fidetype import __version__
    from fidetype.streams.spec import SPEC_VERSION

    print(f"fidetype {__version__} (NeuralTextStream spec {SPEC_VERSION})")
    return 0


#: name -> (function, one-line help, same as)
COMMANDS: dict[str, tuple[Callable[[list[str]], int], str, str]] = {
    "validate": (_validate, "check stream files for NeuralTextStream conformance", "python -m fidetype.conformance check"),
    "trust": (_trust, "run the streaming trust layer on stream files; print decisions", "python -m fidetype.trust.streaming replay"),
    "replay": (_trust, "same as 'trust'", "python -m fidetype.trust.streaming replay"),
    "demo": (_demo, "offline demo: synthetic decoder streams through the trust layer", "python -m fidetype.demo"),
    "conformance": (_conformance, "the full conformance suite (check, consumer, vectors)", "python -m fidetype.conformance"),
    "lsl": (_lsl, "Lab Streaming Layer input and output (needs the [lsl] extra)", "python -m fidetype.adapters.lsl"),
    "benchmark": (_benchmark, "open benchmark v0.1 (tracks, prepare, score, leaderboard)", "python -m fidetype.benchmark"),
    "ledger": (_ledger, "provenance ledger tools (verify, report)", "python -m fidetype.trust.provenance"),
    "version": (_version, "print the package and spec versions", ""),
}


def _usage() -> str:
    lines = ["usage: fidetype <command> [options]", "", "Fidetype: a trust layer for neural text entry.", "",
             "commands:"]
    for name, (_, help_, _same) in COMMANDS.items():
        lines.append(f"  {name:<12} {help_}")
    lines += ["", "Run 'fidetype <command> --help' for the options of one command."]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of the ``fidetype`` console script."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(_usage())
        return 0
    if args[0] in ("-V", "--version"):
        return _version([])
    cmd = COMMANDS.get(args[0])
    if cmd is None:
        print(f"fidetype: unknown command {args[0]!r}\n", file=sys.stderr)
        print(_usage(), file=sys.stderr)
        return 2
    try:
        rc = cmd[0](args[1:])
    except SystemExit as e:  # argparse exits on --help and on usage errors
        code = e.code
        return code if isinstance(code, int) else (0 if code is None else 1)
    return int(rc or 0)


if __name__ == "__main__":
    raise SystemExit(main())
