#!/usr/bin/env python3
"""Verify selected current artifacts against explicit path and SHA-256 bindings."""

import argparse
import json
from pathlib import Path
import sys

from artifact_bindings import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Root for relative binding paths")
    parser.add_argument("--bindings", type=Path, required=True, help="JSON list or {bindings: [...]} file")
    parser.add_argument("--output", type=Path, required=True, help="JSON report path")
    args = parser.parse_args()
    try:
        report = verify(args.bindings, args.root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        report = {"valid": False, "root": str(args.root), "bindings": str(args.bindings), "mismatches": [{"reason": "input_error", "message": str(error)}], "verified": []}
    if args.output.exists():
        report["valid"] = False
        report["mismatches"].append({"reason": "output_exists", "path": str(args.output)})
        print(json.dumps(report, indent=2))
        return 1
    try:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
    except OSError as error:
        report["valid"] = False
        report["mismatches"].append({"reason": "output_error", "path": str(args.output), "message": str(error)})
        print(json.dumps(report, indent=2))
        return 1
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
