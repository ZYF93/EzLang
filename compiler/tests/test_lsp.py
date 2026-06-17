import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lsp.server import (
    EzLanguageServer,
    analyze_document,
    analyze_document_with_workspace,
    declaration_at,
    definition_at,
    document_symbols,
    format_document,
    index_document,
    inlay_hints,
    semantic_tokens,
)


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
    formatted = format_document('let value:I32=1;\nstruct Data{ val:I32; };\nconst main=():I32=>{ const nested=flow{ const p=parallel{ return 1; }; return p; }; return nested; };\n')

    assert formatted == 'let value: I32 = 1;\nstruct Data { val: I32; };\nconst main = (): I32 => { const nested = flow { const p = parallel { return 1; }; return p; }; return nested; };\n'


def test_lsp_initialize_advertises_editor_features():
    capabilities = EzLanguageServer()._initialize({})["capabilities"]

    assert capabilities["hoverProvider"] is True
    assert capabilities["definitionProvider"] is True
    assert capabilities["documentSymbolProvider"] is True
    assert capabilities["documentFormattingProvider"] is True
    assert capabilities["inlayHintProvider"] is True
    assert "completionProvider" in capabilities


def test_lsp_hover_metadata_uses_std_comments(tmp_path):
    source = 'from "std/io" import { println };\nprintln(msg = "ok");\n'

    declaration = declaration_at(source, "println", tmp_path, ROOT)

    assert declaration is not None
    assert "追加换行" in declaration.documentation
    assert "println" in declaration.signature


def test_lsp_hover_metadata_includes_struct_definition():
    source = '// 用户数据。\nstruct User {\n    name: Str;\n    age: I32;\n};\nlet value: User;\n'

    declaration = declaration_at(source, "User", Path.cwd(), ROOT)

    assert declaration is not None
    assert "struct User" in declaration.definition
    assert "name: Str" in declaration.definition
    assert "用户数据" in declaration.documentation


def test_lsp_hover_describes_builtin_types():
    server = EzLanguageServer()
    uri = "file:///tmp/main.ez"
    server.documents[uri] = "let err: Error;\nlet value: I32;\n"

    error_hover = server._hover({"textDocument": {"uri": uri}, "position": {"line": 0, "character": 10}})
    int_hover = server._hover({"textDocument": {"uri": uri}, "position": {"line": 1, "character": 12}})

    assert error_hover is not None
    assert "内置错误类型" in error_hover["contents"]["value"]
    assert "toString" in error_hover["contents"]["value"]
    assert int_hover is not None
    assert "32 位有符号整数" in int_hover["contents"]["value"]


def test_lsp_hover_prefers_inferred_type_summary():
    server = EzLanguageServer()
    uri = "file:///tmp/main.ez"
    server.documents[uri] = '''
type Named = { name: Str };
struct Data { val: I32; };
const create = (name: Str): Named => { return { name = name }; };
const data = Data(val = 1);
const fn = create;
const dict: Dict<Str, I32>;
'''

    data_hover = server._hover({"textDocument": {"uri": uri}, "position": {"line": 4, "character": 7}})
    fn_hover = server._hover({"textDocument": {"uri": uri}, "position": {"line": 5, "character": 7}})
    dict_hover = server._hover({"textDocument": {"uri": uri}, "position": {"line": 6, "character": 7}})
    alias_hover = server._hover({"textDocument": {"uri": uri}, "position": {"line": 3, "character": 28}})

    assert data_hover is not None
    assert "data: struct { val: I32 }" in data_hover["contents"]["value"]
    assert fn_hover is not None
    assert "fn: (name: Str) => Named" in fn_hover["contents"]["value"]
    assert dict_hover is not None
    assert "dict: { Str: I32 }" in dict_hover["contents"]["value"]
    assert alias_hover is not None
    assert "Named" in alias_hover["contents"]["value"]
    assert "[Named](file:///tmp/main.ez#L2," in fn_hover["contents"]["value"]


def test_lsp_semantic_tokens_marks_named_argument_and_suspend(tmp_path):
    source = '''
from "std/io" import { println, readLine };
const main = (): Void => {
    println(msg = "ok");
    readLine();
};
'''

    tokens = semantic_tokens(source, tmp_path, ROOT)

    assert tokens
    assert len(tokens) % 5 == 0
    assert 0 in tokens[3::5]
    assert 3 in tokens[4::5]


def test_lsp_inlay_hint_marks_suspend_source_and_transitive_function(tmp_path):
    source = '''
from "std/io" import { readLine };
const readName = (): Str? => {
    return readLine();
};
const main = (): Void => {
    readName();
};
'''

    hints = inlay_hints(source, tmp_path, ROOT)
    labels = [hint["label"].strip() for hint in hints]

    assert labels.count("suspend") >= 2


def test_lsp_does_not_report_imported_symbols_as_undefined(tmp_path):
    source = 'from "std/io" import { println };\nprintln(msg = "ok");\n'

    diagnostics, _ = analyze_document_with_workspace(source, tmp_path, ROOT)

    assert diagnostics == []


def test_lsp_ignores_packaged_std_extern_missing_files(tmp_path):
    std_root = tmp_path / "packages" / "std"
    std_root.mkdir(parents=True)
    source = 'extern "@std/native/time.c" for linux;\nexport declare const sleep: (ms: I64) => Void;\n'
    module = std_root / "time.ez"
    module.write_text(source, encoding="utf-8")

    diagnostics, _ = analyze_document_with_workspace(source, module.parent, tmp_path)

    assert diagnostics == []


def test_lsp_suspend_hint_is_before_call_and_definition(tmp_path):
    source = '''
from "std/time" import { sleep };
const main = (): Void => {
    sleep(ms = 10);
};
'''

    hints = inlay_hints(source, tmp_path, ROOT)
    positions = [(hint["position"]["line"], hint["position"]["character"], hint["label"]) for hint in hints]

    assert (2, 6, "suspend ") in positions
    assert (3, 4, "suspend ") in positions
