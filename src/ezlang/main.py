#!/usr/bin/env python3
"""
EzLang Compiler CLI
"""

import sys
import argparse
from ezlang.compiler import EzLangCompiler

def cli():
    parser = argparse.ArgumentParser(description="EzLang Toolchain")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # build command
    build_parser = subparsers.add_parser("build", help="Build project based on config.json")
    build_parser.add_argument("--target", help="Specify target name to build")

    # run command
    run_parser = subparsers.add_parser("run", help="Run an ez script quickly")
    run_parser.add_argument("file", help="Source file to run")

    # test / fmt / lint commands (stubs)
    test_parser = subparsers.add_parser("test", help="Run tests")
    fmt_parser = subparsers.add_parser("fmt", help="Format source files")
    lint_parser = subparsers.add_parser("lint", help="Lint source files")

    args = parser.parse_args()

    if args.command == "build":
        compiler = EzLangCompiler()
        try:
            compiler.build_project(target_name=args.target)
        except Exception as e:
            print(f"Build failed: {e}")
            sys.exit(1)
    elif args.command == "run":
        compiler = EzLangCompiler()
        try:
            with open(args.file, 'r') as f:
                source_code = f.read()
            result = compiler.compile(source_code)
            # 暂时代替执行，输出 IR
            print("--- LLVM IR ---")
            print(result)
        except Exception as e:
            print(f"Run failed: {e}")
            sys.exit(1)
    elif args.command in ("test", "fmt", "lint"):
        print(f"Command '{args.command}' is not fully implemented yet.")
    else:
        parser.print_help()

def main():
    cli()

if __name__ == "__main__":
    main()