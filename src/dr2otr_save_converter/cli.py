"""Command-line interface for the DR2 OTR save converter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .converter import convert_and_write


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dr2otr-save",
        description=(
            "Convert an extracted Dead Rising 2: Off the Record Xbox 360 "
            "Story Mode payload into a new native-PC artifact."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    convert = subparsers.add_parser(
        "xbox-to-pc",
        help="convert an extracted Xbox 360 Story Mode payload to native PC",
    )
    convert.add_argument(
        "--xbox-save",
        type=Path,
        required=True,
        help="inner Xbox-format DCSAV01.DSF payload, not a signed STFS package",
    )
    convert.add_argument(
        "--pc-template",
        type=Path,
        required=True,
        help="a native-PC story-only save containing at least one carried item",
    )
    convert.add_argument("--output", type=Path, required=True)
    convert.add_argument(
        "--audit",
        type=Path,
        help="audit JSON path (default: OUTPUT.audit.json)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "xbox-to-pc":
        raise RuntimeError(f"unhandled command: {args.command}")
    try:
        written = convert_and_write(
            args.xbox_save,
            args.pc_template,
            args.output,
            args.audit,
        )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    summary = written.result.audit.get("decoded_header")
    items = written.result.audit.get("items")
    output = written.result.audit.get("output")
    if not isinstance(items, dict) or not isinstance(output, dict):
        print("error: converter returned an incomplete audit", file=sys.stderr)
        return 2
    print(f"output={written.output_path}")
    print(f"audit={written.audit_path}")
    print(f"sha256={output.get('sha256')}")
    print(f"summary={summary}")
    print(f"active_items={items.get('active_names')}")
    print("sandbox=omitted")
    print("status=offline-validated")
    return 0
