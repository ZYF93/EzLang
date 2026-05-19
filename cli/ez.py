#!/usr/bin/env python3
"""EzLang CLI toolchain entry point."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="ez",
        description="EzLang programming language toolchain"
    )
    parser.add_argument("--version", action="version", version="ez 0.1.0")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # build command
    build_parser = subparsers.add_parser("build", help="Build EzLang project")
    build_parser.add_argument("--target", help="Target platform (linux, macos, windows, android, ios, emcc)")
    build_parser.add_argument("--optimize", "-O", type=int, default=2, help="Optimization level (0-3)")

    # run command
    run_parser = subparsers.add_parser("run", help="Run EzLang project")
    run_parser.add_argument("file", nargs="?", help="File to run")

    # other commands
    subparsers.add_parser("install", help="Install dependencies")
    subparsers.add_parser("fmt", help="Format source files")
    subparsers.add_parser("release", help="Release package")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    print(f"Command '{args.command}' not implemented yet")
    return 1


if __name__ == "__main__":
    sys.exit(main())
