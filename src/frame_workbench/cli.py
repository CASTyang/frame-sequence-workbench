"""Console interface."""

import argparse
import json
import sys
import zipfile

from .pipeline import build


def main(argv=None):
    parser = argparse.ArgumentParser(description="Normalize PNG sequences and export animation assets offline.")
    parser.add_argument("--version", action="version", version="frame-sequence-workbench 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("build", help="build a JSON configuration into a new output directory")
    command.add_argument("config")
    command.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        manifest = build(args.config, args.output)
    except (ValueError, OSError, zipfile.BadZipFile, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "output": args.output,
                "frame_count": manifest["frame_count"],
                "total_duration_ms": manifest["total_duration_ms"],
            }
        )
    )
    return 0
