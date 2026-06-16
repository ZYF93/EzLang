import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lsp.server import EzLanguageServer, analyze_document, definition_at, document_symbols, format_document, index_document


def test_lsp_reports_syntax_diagnostic(tmp_path):
    diagnostics, analyzer = analyze_document('let value: I32 = ;\n', tmp_path)

    assert analyzer is None
    assert diagnostics
    assert diagnostics[0]["severity"] == 1
    assert "语法错误" in diagnostics[0]["message"]


def test_lsp_reports_semantic_diagnostic(tmp_path):
    diagnostics, analyzer = analyze_document('let value: I32 = missing;\n', tmp_path)

    assert analyzer is not None
    assert diagnostics
    assert "未定义的变量" in diagnostics[0]["message"]


def test_lsp_accepts_valid_source(tmp_path):
    diagnostics, analyzer = analyze_document('let value: I32 = 1;\n', tmp_path)

    assert analyzer is not None
    assert diagnostics == []


def test_lsp_indexes_declarations_with_kinds():
    declarations = index_document('struct User { name: Str; }\nlet make = (): I32 => { return 1; };\nconst count: I32 = 1;\n')

    assert declarations["User"].line == 0
    assert declarations["make"].kind.name == "FUNCTION"
    assert declarations["count"].kind.name == "CONSTANT"


def test_lsp_definition_finds_local_symbol(tmp_path):
    source = 'let value: I32 = 1;\nlet next: I32 = value;\n'
    location = definition_at(source, tmp_path.joinpath("main.ez").as_uri(), 1, 17, tmp_path, tmp_path)

    assert location is not None
    assert location["range"]["start"] == {"line": 0, "character": 4}


def test_lsp_definition_finds_imported_symbol(tmp_path):
    module = tmp_path / "lib.ez"
    module.write_text('export let answer: I32 = 42;\n', encoding="utf-8")
    source = 'from "lib" import { answer };\nlet value: I32 = answer;\n'

    location = definition_at(source, tmp_path.joinpath("main.ez").as_uri(), 1, 17, tmp_path, tmp_path)

    assert location is not None
    assert location["uri"] == module.as_uri()
    assert location["range"]["start"] == {"line": 0, "character": 11}


def test_lsp_definition_finds_aliased_import_source(tmp_path):
    module = tmp_path / "lib.ez"
    module.write_text('export let answer: I32 = 42;\n', encoding="utf-8")
    source = 'from "lib" import { answer as ans };\nlet value: I32 = ans;\n'

    location = definition_at(source, tmp_path.joinpath("main.ez").as_uri(), 1, 17, tmp_path, tmp_path)

    assert location is not None
    assert location["uri"] == module.as_uri()
    assert location["range"]["start"] == {"line": 0, "character": 11}


def test_lsp_definition_finds_std_declare_symbol(tmp_path):
    source = 'from "std/io" import { println };\nprintln(msg = "ok");\n'

    location = definition_at(source, tmp_path.joinpath("main.ez").as_uri(), 1, 2, tmp_path, ROOT)

    assert location is not None
    assert location["uri"].endswith("/packages/std/io.ez")
    assert location["range"]["start"]["line"] >= 0


def test_lsp_document_symbols_include_top_level_declarations(tmp_path):
    symbols = document_symbols('struct User { name: Str; }\nlet make = (): I32 => { return 1; };\n', tmp_path.joinpath("main.ez").as_uri())

    assert [symbol["name"] for symbol in symbols] == ["User", "make"]


def test_lsp_format_document_reuses_cli_formatter():
    formatted = format_document('let value:I32=1;\nloop {value=value+1;}\n')

    assert formatted == 'let value: I32 = 1;\nloop {\n    value = value + 1;\n}\n'


def test_lsp_initialize_advertises_editor_features():
    capabilities = EzLanguageServer()._initialize({})["capabilities"]

    assert capabilities["hoverProvider"] is True
    assert capabilities["definitionProvider"] is True
    assert capabilities["documentSymbolProvider"] is True
    assert capabilities["documentFormattingProvider"] is True
    assert "completionProvider" in capabilities
