"""Parser tests for EzLang."""

import pytest
from pathlib import Path

try:
    from antlr4 import InputStream, CommonTokenStream
    from parser.EzLangLexer import EzLangLexer
    from parser.EzLangParser import EzLangParser
    HAS_PARSER = True
except ImportError:
    HAS_PARSER = False

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


def parse_string(code: str):
    """Parse a string of EzLang code."""
    input_stream = InputStream(code)
    lexer = EzLangLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = EzLangParser(stream)
    tree = parser.compilationUnit()
    return parser, tree


@pytest.mark.skipif(not HAS_PARSER, reason="Parser not generated")
class TestBasicParsing:
    """Test basic parsing functionality."""

    def test_parse_empty(self):
        """Parse empty input."""
        parser, tree = parse_string("")
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_variable_decl(self):
        """Parse variable declarations."""
        code = """
        let x: I32 = 42;
        const y: Str = "hello";
        static z: Bool = true;
        """
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_basic_types(self):
        """Parse basic types."""
        code = """
        let a: I8 = 1;
        let b: I32 = 2;
        let c: I64 = 3;
        let d: U8 = 4;
        let e: U32 = 5;
        let f: U64 = 6;
        let g: F32 = 1.0;
        let h: F64 = 2.0;
        let i: Str = "test";
        let j: Bool = false;
        """
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_optional_type(self):
        """Parse optional types."""
        code = "let x: I32? = 42;"
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_union_type(self):
        """Parse union types."""
        code = "let x: I32 | Str = \"hello\";"
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_array_type(self):
        """Parse array types."""
        code = "let x: I32[] = [1, 2, 3];"
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_vec_type(self):
        """Parse SIMD vector types."""
        code = "let x: Vec<I32>[4] = Vec[1, 2, 3, 4];"
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_struct(self):
        """Parse struct declarations."""
        code = """
        struct Point {
            x: I32;
            y: I32 = 0;
        };
        """
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_struct_with_spread(self):
        """Parse struct with spread."""
        code = """
        struct Point3D {
            ...Point;
            z: I32;
        };
        """
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_function(self):
        """Parse function declarations."""
        code = """
        const add = (a: I32, b: I32 = 1) => {
            return a + b;
        };
        """
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_call(self):
        """Parse function calls."""
        code = """
        const result = add(a = 1, b = 2);
        """
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_if_like(self):
        """Parse if-like expressions."""
        code = """
        (x > 0) ? print(msg = "yes");
        """
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_loop(self):
        """Parse loop expressions."""
        code = """
        loop i in 0...10 {
            print(msg = i);
        }
        """
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_match(self):
        """Parse match expressions."""
        code = """
        match {
            (x == 0) ? { return 1; },
            (x == 1) ? { return 2; },
            (true) ? { return 3; }
        };
        """
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_flow(self):
        """Parse flow blocks."""
        code = """
        const result = flow {
            const a = fetchA();
            const b = fetchB();
            return a + b;
        };
        """
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_catch_throw(self):
        """Parse catch and throw."""
        code = """
        const err = catch {
            throw Error(code = 404);
        };
        """
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_import(self):
        """Parse import declarations."""
        code = 'from "./std.ez" import { print, println };';
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_extern(self):
        """Parse extern declarations."""
        code = 'extern "./libs/libcrypto.a" for linux;';
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_declare(self):
        """Parse declare declarations."""
        code = "declare const hash: (data: Blob) => Blob;"
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_type_alias(self):
        """Parse type alias declarations."""
        code = """
        type Point = {
            x: I32;
            y: I32;
        };
        """
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_parse_operators(self):
        """Parse binary operators."""
        code = """
        let a = 1 + 2 * 3;
        let b = (1 + 2) * 3;
        let c = x & y | z;
        let d = x && y || z;
        let e = x == y;
        let f = x < y;
        let g = x << 2;
        let h = !x;
        """
        parser, tree = parse_string(code)
        assert parser.getNumberOfSyntaxErrors() == 0


@pytest.mark.skipif(not HAS_PARSER, reason="Parser not generated")
class TestExampleFiles:
    """Test parsing example files."""

    def test_basics_ez(self):
        """Parse basics.ez."""
        path = EXAMPLES_DIR / "basics.ez"
        parser, tree = parse_string(path.read_text())
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_types_ez(self):
        """Parse types.ez."""
        path = EXAMPLES_DIR / "types.ez"
        parser, tree = parse_string(path.read_text())
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_structs_ez(self):
        """Parse structs.ez."""
        path = EXAMPLES_DIR / "structs.ez"
        parser, tree = parse_string(path.read_text())
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_functions_ez(self):
        """Parse functions.ez."""
        path = EXAMPLES_DIR / "functions.ez"
        parser, tree = parse_string(path.read_text())
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_control_ez(self):
        """Parse control.ez."""
        path = EXAMPLES_DIR / "control.ez"
        parser, tree = parse_string(path.read_text())
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_operators_ez(self):
        """Parse operators.ez."""
        path = EXAMPLES_DIR / "operators.ez"
        parser, tree = parse_string(path.read_text())
        assert parser.getNumberOfSyntaxErrors() == 0

    def test_simd_ez(self):
        """Parse simd.ez."""
        path = EXAMPLES_DIR / "simd.ez"
        parser, tree = parse_string(path.read_text())
        assert parser.getNumberOfSyntaxErrors() == 0
