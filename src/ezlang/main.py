#!/usr/bin/env python3
"""
EzLang Compiler CLI
"""

import sys
from ezlang.compiler import EzLangCompiler

def main():
    if len(sys.argv) != 2:
        print("Usage: python -m ezlang <source_file.ez>")
        sys.exit(1)

    source_file = sys.argv[1]
    with open(source_file, 'r') as f:
        source_code = f.read()

    compiler = EzLangCompiler()
    result = compiler.compile(source_code)
    print(result)

if __name__ == "__main__":
    main()