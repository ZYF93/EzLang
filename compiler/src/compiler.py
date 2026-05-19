"""EzLang compiler main entry point."""

import sys
from pathlib import Path

try:
    from antlr4 import FileStream, CommonTokenStream
    from parser.EzLangLexer import EzLangLexer
    from parser.EzLangParser import EzLangParser
    from parser.ast_builder import ASTBuilder
    HAS_PARSER = True
except ImportError:
    HAS_PARSER = False


class Compiler:
    """EzLang compiler."""

    def __init__(self, verbose=False):
        self.verbose = verbose

    def parse_file(self, filepath: str):
        """Parse an EzLang source file."""
        if not HAS_PARSER:
            raise RuntimeError(
                "Parser not generated. Please run:\n"
                "  cd grammar && java -jar ~/.antlr/antlr-4.13.2-complete.jar "
                "-Dlanguage=Python3 -o ../compiler/src/parser EzLang.g4"
            )

        if self.verbose:
            print(f"Parsing {filepath}...")

        input_stream = FileStream(filepath, encoding='utf-8')
        lexer = EzLangLexer(input_stream)
        stream = CommonTokenStream(lexer)
        parser = EzLangParser(stream)
        tree = parser.compilationUnit()

        if parser.getNumberOfSyntaxErrors() > 0:
            raise SyntaxError(f"Found {parser.getNumberOfSyntaxErrors()} syntax errors")

        # Build AST
        builder = ASTBuilder()
        ast = builder.visit(tree)
        return ast

    def compile(self, filepath: str, output_path: str = None):
        """Compile an EzLang source file."""
        ast = self.parse_file(filepath)
        # TODO: semantic analysis, code generation
        if self.verbose:
            print(f"Parsed successfully: {type(ast).__name__}")
        return ast


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="EzLang compiler")
    parser.add_argument("file", help="Source file to compile")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--parse-only", action="store_true", help="Only parse, don't generate code")

    args = parser.parse_args()

    compiler = Compiler(verbose=args.verbose)

    try:
        ast = compiler.compile(args.file, args.output)
        if args.verbose:
            print("Compilation successful!")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
