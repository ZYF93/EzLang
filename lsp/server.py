"""EzLang Language Server Protocol 服务端。"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
COMPILER_SRC = ROOT / "compiler" / "src"
if str(COMPILER_SRC) not in sys.path:
    sys.path.insert(0, str(COMPILER_SRC))

from antlr4 import CommonTokenStream, InputStream  # noqa: E402
from antlr4.error.ErrorListener import ErrorListener  # noqa: E402
from parser.EzLangLexer import EzLangLexer  # noqa: E402
from parser.EzLangParser import EzLangParser  # noqa: E402
from semantic.analyzer import analyze  # noqa: E402
from semantic.symbols import Symbol, SymbolKind  # noqa: E402

try:  # noqa: E402
    from cli.ez import _format_ez_source
except Exception:  # pragma: no cover - CLI 依赖异常时格式化能力降级
    _format_ez_source = None


TOKEN_TYPES = {
    "LET": "关键字",
    "CONST": "关键字",
    "STATIC": "关键字",
    "STRUCT": "关键字",
    "TYPE": "关键字",
    "DECLARE": "关键字",
    "LOOP": "关键字",
    "BREAK": "关键字",
    "CONTINUE": "关键字",
    "IMPORT": "关键字",
    "EXPORT": "关键字",
    "FROM": "关键字",
    "MATCH": "关键字",
    "CATCH": "关键字",
    "THROW": "关键字",
    "FLOW": "关键字",
    "PARALLEL": "关键字",
    "RETURN": "关键字",
    "EXTERN": "关键字",
    "I8": "类型",
    "I32": "类型",
    "I64": "类型",
    "U8": "类型",
    "U32": "类型",
    "U64": "类型",
    "F32": "类型",
    "F64": "类型",
    "STR": "类型",
    "BOOL": "类型",
    "VOID": "类型",
    "VEC": "类型",
    "LIST": "类型",
}

KEYWORD_COMPLETIONS = [
    "let", "const", "static", "struct", "type", "declare", "export", "from", "import",
    "loop", "break", "continue", "match", "catch", "throw", "flow", "parallel", "return",
    "extern", "true", "false",
]
TYPE_COMPLETIONS = ["I8", "I32", "I64", "U8", "U32", "U64", "F32", "F64", "Str", "Bool", "Void", "Vec", "List", "Dict"]
STD_MODULES = [
    "std/io", "std/fmt", "std/str", "std/math", "std/time", "std/fs", "std/path", "std/log",
    "std/os", "std/random", "std/collections", "std/hash", "std/regex", "std/crypto",
    "std/net/http", "std/net/tcp", "std/net/ws",
]

COMPLETION_KIND_KEYWORD = 14
COMPLETION_KIND_FUNCTION = 3
COMPLETION_KIND_VARIABLE = 6
COMPLETION_KIND_MODULE = 9
COMPLETION_KIND_STRUCT = 22
COMPLETION_KIND_TYPE = 25
SYMBOL_KIND_FILE = 1
SYMBOL_KIND_MODULE = 2
SYMBOL_KIND_CLASS = 5
SYMBOL_KIND_METHOD = 6
SYMBOL_KIND_FUNCTION = 12
SYMBOL_KIND_VARIABLE = 13
SYMBOL_KIND_CONSTANT = 14
SYMBOL_KIND_STRUCT = 23
SYMBOL_KIND_TYPE = 26
DIAGNOSTIC_ERROR = 1
DIAGNOSTIC_WARNING = 2
SEMANTIC_TOKEN_TYPES = ["parameter", "function", "class", "type", "keyword"]
SEMANTIC_TOKEN_MODIFIERS = ["declaration", "readonly", "modification", "async"]
SEMANTIC_TOKEN_TYPE_INDEX = {name: index for index, name in enumerate(SEMANTIC_TOKEN_TYPES)}
SEMANTIC_TOKEN_MODIFIER_INDEX = {name: index for index, name in enumerate(SEMANTIC_TOKEN_MODIFIERS)}

DECLARATION_PATTERNS = [
    (re.compile(r"\b(?:export\s+)?struct\s+([A-Z][A-Za-z0-9_]*)"), SymbolKind.STRUCT),
    (re.compile(r"\b(?:export\s+)?type\s+([A-Z][A-Za-z0-9_]*)"), SymbolKind.TYPE_ALIAS),
    (re.compile(r"\b(?:export\s+)?declare\s+(?:let|const|static)\s+((?:[a-z_][A-Za-z0-9_]*|\$[A-Za-z0-9_]+)(?:\.[a-z_][A-Za-z0-9_]*)*)"), SymbolKind.EXTERN_DECLARE),
    (re.compile(r"\b(?:export\s+)?(?:let|const|static)\s+((?:[a-z_][A-Za-z0-9_]*|\$[A-Za-z0-9_]+)(?:\.[a-z_][A-Za-z0-9_]*)*)"), SymbolKind.VARIABLE),
]
IMPORT_RE = re.compile(r'\bfrom\s+"([^"]+)"\s+import\s*\{([^}]*)\}', re.S)
IMPORT_PREFIX_RE = re.compile(r'from\s+"([^"]+)"\s+import\s*\{[^}]*$')
SUSPEND_SOURCES = {
    "sleep", "fetch", "fetchEx", "readFile", "writeFile", "appendFile", "start",
    "tcpConnect", "tcpConnectTimeout", "tcpTlsConnect", "tcpTlsRead", "tcpTlsWrite",
    "tcpListen", "tcpAccept", "tcpAcceptTimeout", "tcpRead", "tcpReadTimeout",
    "tcpWrite", "tcpWriteTimeout", "udpBind", "udpRecvFrom", "udpRecvFromTimeout",
    "udpRecvTimeout", "udpSendTimeout", "wsConnect", "wsRecv", "streamRead",
    "streamWrite", "streamCopy", "processExec", "processSpawn", "processWait", "readLine",
}
CALL_RE = re.compile(r'\b([a-z_][A-Za-z0-9_]*|\$[A-Za-z0-9_]+)\s*(?:<[^>]+>\s*)?\(')


@dataclass
class SyntaxDiagnostic:
    line: int
    column: int
    message: str
    token_text: str = ""


@dataclass
class Declaration:
    name: str
    kind: SymbolKind
    line: int
    character: int
    end_character: int
    uri: str | None = None
    signature: str = ""
    documentation: str = ""
    suspend: bool = False
    definition: str = ""

    def location(self, fallback_uri: str) -> dict[str, Any]:
        uri = self.uri or fallback_uri
        return {
            "uri": uri,
            "range": {
                "start": {"line": self.line, "character": self.character},
                "end": {"line": self.line, "character": self.end_character},
            },
        }


@dataclass
class ImportBinding:
    name: str
    source_name: str
    module: str
    line: int
    character: int


class _SyntaxErrorCollector(ErrorListener):
    """收集 ANTLR 语法错误并保留 LSP 需要的位置。"""

    def __init__(self) -> None:
        self.errors: list[SyntaxDiagnostic] = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):  # noqa: N802
        token_text = getattr(offendingSymbol, "text", "") or ""
        detail = f"语法错误: {msg}"
        if token_text:
            detail += f"，附近 token: '{token_text}'"
        self.errors.append(SyntaxDiagnostic(line=line, column=column, message=detail, token_text=token_text))


class EzLanguageServer:
    """最小 LSP 服务端，使用标准输入输出与 VS Code 通信。"""

    def __init__(self) -> None:
        self.documents: dict[str, str] = {}
        self.workspace_root = ROOT
        self.shutdown_requested = False

    def serve(self) -> int:
        while True:
            message = self._read_message()
            if message is None:
                return 0
            response = self._handle_message(message)
            if response is not None:
                self._send(response)

    def _read_message(self) -> dict[str, Any] | None:
        headers: dict[str, str] = {}
        while True:
            line = sys.stdin.buffer.readline()
            if line == b"":
                return None
            line = line.decode("ascii", errors="replace").strip()
            if not line:
                break
            key, _, value = line.partition(":")
            headers[key.lower()] = value.strip()
        length = int(headers.get("content-length", "0"))
        if length <= 0:
            return None
        payload = sys.stdin.buffer.read(length)
        return json.loads(payload.decode("utf-8"))

    def _send(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        sys.stdout.buffer.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii"))
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()

    def _handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        try:
            if method == "initialize":
                return self._response(message, self._initialize(message.get("params") or {}))
            if method == "initialized":
                return None
            if method == "textDocument/didOpen":
                params = message.get("params") or {}
                document = params.get("textDocument") or {}
                self.documents[document.get("uri", "")] = document.get("text", "")
                self._publish_diagnostics(document.get("uri", ""))
                return None
            if method == "textDocument/didChange":
                params = message.get("params") or {}
                uri = (params.get("textDocument") or {}).get("uri", "")
                changes = params.get("contentChanges") or []
                if changes:
                    self.documents[uri] = changes[-1].get("text", "")
                self._publish_diagnostics(uri)
                return None
            if method == "textDocument/didSave":
                uri = ((message.get("params") or {}).get("textDocument") or {}).get("uri", "")
                self._publish_diagnostics(uri)
                return None
            if method == "textDocument/didClose":
                uri = ((message.get("params") or {}).get("textDocument") or {}).get("uri", "")
                self.documents.pop(uri, None)
                self._send_notification("textDocument/publishDiagnostics", {"uri": uri, "diagnostics": []})
                return None
            if method == "textDocument/completion":
                return self._response(message, self._completion(message.get("params") or {}))
            if method == "textDocument/hover":
                return self._response(message, self._hover(message.get("params") or {}))
            if method == "textDocument/definition":
                return self._response(message, self._definition(message.get("params") or {}))
            if method == "textDocument/documentSymbol":
                return self._response(message, self._document_symbol(message.get("params") or {}))
            if method == "textDocument/formatting":
                return self._response(message, self._formatting(message.get("params") or {}))
            if method == "textDocument/inlayHint":
                return self._response(message, self._inlay_hint(message.get("params") or {}))
            if method == "textDocument/semanticTokens/full":
                return self._response(message, self._semantic_tokens(message.get("params") or {}))
            if method == "shutdown":
                self.shutdown_requested = True
                return self._response(message, None)
            if method == "exit":
                raise SystemExit(0 if self.shutdown_requested else 1)
            if "id" in message:
                return self._error_response(message, -32601, f"不支持的方法: {method}")
            return None
        except SystemExit:
            raise
        except Exception as exc:  # pragma: no cover - 防止 LSP 进程静默退出
            print(traceback.format_exc(), file=sys.stderr)
            if "id" in message:
                return self._error_response(message, -32603, str(exc))
            return None

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        root_uri = params.get("rootUri")
        if isinstance(root_uri, str):
            root = _path_from_uri(root_uri)
            if root is not None:
                self.workspace_root = root
        return {
            "capabilities": {
                "textDocumentSync": {"openClose": True, "change": 1, "save": True},
                "completionProvider": {"triggerCharacters": [".", "\"", "<"]},
                "hoverProvider": True,
                "definitionProvider": True,
                "documentSymbolProvider": True,
                "documentFormattingProvider": True,
                "inlayHintProvider": True,
                "semanticTokensProvider": {
                    "legend": {"tokenTypes": SEMANTIC_TOKEN_TYPES, "tokenModifiers": SEMANTIC_TOKEN_MODIFIERS},
                    "full": True,
                },
            },
            "serverInfo": {"name": "ezlang-lsp", "version": "0.1.0"},
        }

    def _publish_diagnostics(self, uri: str) -> None:
        text = self._document_text(uri)
        if text is None:
            return
        diagnostics, _ = analyze_document(text, base_dir=self._base_dir_for_uri(uri, text))
        self._send_notification("textDocument/publishDiagnostics", {"uri": uri, "diagnostics": diagnostics})

    def _completion(self, params: dict[str, Any]) -> dict[str, Any]:
        uri = ((params.get("textDocument") or {}).get("uri")) or ""
        text = self._document_text(uri) or ""
        position = params.get("position") or {}
        prefix = _line_prefix(text, int(position.get("line", 0)), int(position.get("character", 0)))
        items: list[dict[str, Any]] = []
        if re.search(r'from\s+"[^"]*$', prefix):
            items.extend({"label": module, "kind": COMPLETION_KIND_MODULE, "insertText": module} for module in STD_MODULES)
        elif match := IMPORT_PREFIX_RE.search(prefix):
            module_path = match.group(1)
            module_file = _resolve_module_path(module_path, self._base_dir_for_uri(uri, text), self.workspace_root)
            if module_file is not None:
                items.extend(_declaration_completion(decl) for decl in _index_file(module_file).values())
        else:
            items.extend({"label": word, "kind": COMPLETION_KIND_KEYWORD} for word in KEYWORD_COMPLETIONS)
            items.extend({"label": word, "kind": COMPLETION_KIND_TYPE} for word in TYPE_COMPLETIONS)
            _, analyzer = analyze_document(text, base_dir=self._base_dir_for_uri(uri, text))
            if analyzer is not None:
                items.extend(_symbol_completion(symbol) for symbol in analyzer.symbols.global_scope.symbols.values())
        return {"isIncomplete": False, "items": _dedupe_items(items)}

    def _hover(self, params: dict[str, Any]) -> dict[str, Any] | None:
        uri = ((params.get("textDocument") or {}).get("uri")) or ""
        text = self._document_text(uri) or ""
        position = params.get("position") or {}
        word = _word_at(text, int(position.get("line", 0)), int(position.get("character", 0)))
        if not word:
            return None
        token_label = TOKEN_TYPES.get(word.upper())
        if token_label:
            return {"contents": {"kind": "markdown", "value": f"`{word}`\n\nEzLang {token_label}"}}
        declaration = declaration_at(text, word, self._base_dir_for_uri(uri, text), self.workspace_root)
        if declaration is not None:
            return {"contents": {"kind": "markdown", "value": _declaration_markdown(declaration)}}
        _, analyzer = analyze_document(text, base_dir=self._base_dir_for_uri(uri, text))
        if analyzer is not None:
            symbol = analyzer.symbols.global_scope.symbols.get(word)
            if symbol is not None:
                return {"contents": {"kind": "markdown", "value": _symbol_markdown(symbol)}}
        return None

    def _definition(self, params: dict[str, Any]) -> dict[str, Any] | None:
        uri = ((params.get("textDocument") or {}).get("uri")) or ""
        text = self._document_text(uri) or ""
        position = params.get("position") or {}
        location = definition_at(
            text,
            uri,
            int(position.get("line", 0)),
            int(position.get("character", 0)),
            self._base_dir_for_uri(uri, text),
            self.workspace_root,
        )
        return location

    def _document_symbol(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        uri = ((params.get("textDocument") or {}).get("uri")) or ""
        text = self._document_text(uri) or ""
        return document_symbols(text, uri)

    def _formatting(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        uri = ((params.get("textDocument") or {}).get("uri")) or ""
        text = self._document_text(uri) or ""
        formatted = format_document(text)
        if formatted == text:
            return []
        return [{"range": _full_document_range(text), "newText": formatted}]

    def _inlay_hint(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        uri = ((params.get("textDocument") or {}).get("uri")) or ""
        text = self._document_text(uri) or ""
        return inlay_hints(text, self._base_dir_for_uri(uri, text), self.workspace_root)

    def _semantic_tokens(self, params: dict[str, Any]) -> dict[str, Any]:
        uri = ((params.get("textDocument") or {}).get("uri")) or ""
        text = self._document_text(uri) or ""
        return {"data": semantic_tokens(text, self._base_dir_for_uri(uri, text), self.workspace_root)}

    def _document_text(self, uri: str) -> str | None:
        if uri in self.documents:
            return self.documents[uri]
        path = _path_from_uri(uri)
        if path is not None and path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def _base_dir_for_uri(self, uri: str, text: str) -> Path:
        path = _path_from_uri(uri)
        if path is not None and path.suffix == ".ez":
            return path.parent
        return self.workspace_root

    def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    @staticmethod
    def _response(request: dict[str, Any], result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request.get("id"), "result": result}

    @staticmethod
    def _error_response(request: dict[str, Any], code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": code, "message": message}}


def analyze_document(source: str, base_dir: Path) -> tuple[list[dict[str, Any]], Any | None]:
    """返回 LSP 诊断和可选语义分析器。"""
    syntax_errors = _parse_syntax_errors(source)
    diagnostics = [_syntax_diagnostic(error, source) for error in syntax_errors]
    if syntax_errors:
        return diagnostics, None

    analyzer = analyze(source, base_dir=base_dir, allow_top_level_return=True)
    diagnostics.extend(_line_diagnostic(message, source, DIAGNOSTIC_ERROR) for message in analyzer.symbols.errors)
    diagnostics.extend(_line_diagnostic(message, source, DIAGNOSTIC_WARNING) for message in analyzer.symbols.warnings)
    return diagnostics, analyzer


def definition_at(source: str, uri: str, line: int, character: int, base_dir: Path, workspace_root: Path) -> dict[str, Any] | None:
    """查找当前位置标识符的定义位置。"""
    word = _word_at(source, line, character)
    if not word:
        return None
    declarations = index_document(source, uri)
    local = declarations.get(word)
    if local is not None:
        return local.location(uri)

    for binding in _import_bindings(source):
        if binding.name != word:
            continue
        module_file = _resolve_module_path(binding.module, base_dir, workspace_root)
        if module_file is None:
            continue
        imported = _index_file(module_file).get(binding.source_name)
        if imported is not None:
            return imported.location(_uri_from_path(module_file))
    return None


def declaration_at(source: str, word: str, base_dir: Path, workspace_root: Path) -> Declaration | None:
    """查找当前文件或 import 目标里的声明元数据。"""
    local = index_document(source).get(word)
    if local is not None:
        return local
    for binding in _import_bindings(source):
        if binding.name != word:
            continue
        module_file = _resolve_module_path(binding.module, base_dir, workspace_root)
        if module_file is None:
            continue
        imported = _index_file(module_file).get(binding.source_name)
        if imported is not None:
            return imported
    return None


def document_symbols(source: str, uri: str) -> list[dict[str, Any]]:
    """生成 VS Code 大纲使用的文档符号。"""
    return [_declaration_symbol(decl, uri) for decl in index_document(source, uri).values()]


def format_document(source: str) -> str:
    """格式化 EzLang 源码。"""
    if _format_ez_source is None:
        return source
    return _format_ez_source(source)


def inlay_hints(source: str, base_dir: Path, workspace_root: Path) -> list[dict[str, Any]]:
    """生成参数名和 suspend source 提示。"""
    hints: list[dict[str, Any]] = []
    suspend_names = _suspend_names_for_document(source, base_dir, workspace_root)
    for line_number, line in enumerate(source.splitlines()):
        for match in CALL_RE.finditer(line):
            name = match.group(1)
            args_text, _ = _call_args_on_line(line, match.end() - 1)
            if args_text is None:
                continue
            if name in suspend_names:
                hints.append({
                    "position": {"line": line_number, "character": match.end(1)},
                    "label": " suspend",
                    "kind": 1,
                    "tooltip": "suspend source：在 flow 中会传播挂起语义",
                    "paddingLeft": True,
                })
    return hints


def _suspend_names_for_document(source: str, base_dir: Path, workspace_root: Path) -> set[str]:
    suspend_names = set(SUSPEND_SOURCES)
    for binding in _import_bindings(source):
        module_file = _resolve_module_path(binding.module, base_dir, workspace_root)
        if module_file is None:
            continue
        declaration = _index_file(module_file).get(binding.source_name)
        if declaration is not None and declaration.suspend:
            suspend_names.add(binding.name)

    changed = True
    while changed:
        changed = False
        for name, body in _function_bodies(source).items():
            if name in suspend_names:
                continue
            if any(re.search(rf'\b{re.escape(suspend_name)}\s*(?:<[^>]+>\s*)?\(', body) for suspend_name in suspend_names):
                suspend_names.add(name)
                changed = True
    return suspend_names


def _function_bodies(source: str) -> dict[str, str]:
    bodies: dict[str, str] = {}
    pattern = re.compile(r'\b(?:let|const)\s+([a-z_][A-Za-z0-9_]*|\$[A-Za-z0-9_]+)\s*(?:<[^>]+>\s*)?=\s*\([^)]*\)\s*(?::[^=]+)?=>\s*\{', re.S)
    for match in pattern.finditer(source):
        body_start = match.end()
        body_end = _matching_brace(source, body_start - 1)
        if body_end is not None:
            bodies[match.group(1)] = source[body_start:body_end]
    return bodies


def _matching_brace(source: str, open_index: int) -> int | None:
    depth = 0
    in_string = False
    escape = False
    for index in range(open_index, len(source)):
        ch = source[index]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def index_document(source: str, uri: str | None = None) -> dict[str, Declaration]:
    """轻量索引当前文件的顶层声明。"""
    declarations: dict[str, Declaration] = {}
    lines = source.splitlines()
    for line_number, line in enumerate(lines):
        stripped = line.lstrip()
        offset = len(line) - len(stripped)
        for pattern, kind in DECLARATION_PATTERNS:
            match = pattern.search(stripped)
            if match is None:
                continue
            name = match.group(1).split(".")[-1]
            actual_kind = _declaration_kind_from_line(stripped, kind, match.end(1))
            start = offset + match.start(1) + match.group(1).rfind(name)
            definition = _definition_snippet(source, line_number, actual_kind, offset + match.start(0))
            signature = _signature_from_definition(definition or stripped)
            documentation = _join_documentation(_leading_doc(lines, line_number), _inline_doc_before(stripped[:match.start(0)]))
            declarations[name] = Declaration(
                name=name,
                kind=actual_kind,
                line=line_number,
                character=start,
                end_character=start + len(name),
                uri=uri,
                signature=signature,
                documentation=documentation,
                suspend=_is_suspend_source(name, stripped),
                definition=definition,
            )
            break
    return declarations


def _signature_from_line(line: str) -> str:
    signature = re.sub(r"^export\s+", "", line.strip()).rstrip(";")
    signature = re.sub(r"\s*=>\s*.*$", "", signature)
    return signature


def _signature_from_definition(definition: str) -> str:
    first_line = definition.strip().splitlines()[0] if definition.strip() else ""
    return _signature_from_line(first_line)


def _definition_snippet(source: str, line_number: int, kind: SymbolKind, declaration_start: int | None = None) -> str:
    lines = source.splitlines()
    if line_number < 0 or line_number >= len(lines):
        return ""
    start_offset = sum(len(line) + 1 for line in lines[:line_number])
    if declaration_start is not None:
        start_offset += declaration_start - (len(lines[line_number]) - len(lines[line_number].lstrip()))
    line = lines[line_number]
    stripped = source[start_offset:source.find("\n", start_offset) if source.find("\n", start_offset) >= 0 else len(source)].strip()
    if kind == SymbolKind.STRUCT:
        open_index = source.find("{", start_offset)
        if open_index >= 0:
            close_index = _matching_brace(source, open_index)
            if close_index is not None:
                end = close_index + 1
                if end < len(source) and source[end:end + 1] == ";":
                    end += 1
                return source[start_offset:end].strip()
    if kind == SymbolKind.FUNCTION:
        arrow = source.find("=>", start_offset)
        if arrow >= 0:
            brace = source.find("{", arrow)
            line_end = source.find("\n", start_offset)
            line_end = len(source) if line_end < 0 else line_end
            if brace >= 0 and brace < line_end + 1:
                return source[start_offset:brace].strip()
    return stripped


def _inline_doc_before(prefix: str) -> str:
    comments = [part.strip() for part in prefix.split("//") if part.strip()]
    docs = [comment for comment in comments if not comment.startswith("===")]
    return "\n".join(docs)


def _join_documentation(*parts: str) -> str:
    return "\n".join(part for part in parts if part)


def _leading_doc(lines: list[str], line_number: int) -> str:
    docs: list[str] = []
    index = line_number - 1
    while index >= 0:
        stripped = lines[index].strip()
        if stripped.startswith("//"):
            text = stripped[2:].strip()
            if not text.startswith("==="):
                docs.append(text)
            index -= 1
            continue
        if stripped == "":
            index -= 1
            continue
        break
    docs.reverse()
    return "\n".join(docs)


def _is_suspend_source(name: str, line: str) -> bool:
    if name in SUSPEND_SOURCES:
        return True
    return "@suspend" in line or "suspend source" in line or "挂起" in line


def _declaration_markdown(declaration: Declaration) -> str:
    signature = declaration.definition or declaration.signature or declaration.name
    lines = [f"```ez\n{signature}\n```"]
    if declaration.suspend:
        lines.append("`suspend source`：在 `flow` 中会传播挂起语义。")
    if declaration.documentation:
        lines.append(declaration.documentation)
    return "\n\n".join(lines)


def semantic_tokens(source: str, base_dir: Path, workspace_root: Path) -> list[int]:
    """生成 VS Code semantic token，用于参数名、类型、函数和 suspend 调用着色。"""
    raw_tokens: list[tuple[int, int, int, str, list[str]]] = []
    suspend_names = _suspend_names_for_document(source, base_dir, workspace_root)
    known_types = set(TYPE_COMPLETIONS)
    known_types.update(name for name, decl in index_document(source).items() if decl.kind in (SymbolKind.STRUCT, SymbolKind.TYPE_ALIAS))
    for binding in _import_bindings(source):
        module_file = _resolve_module_path(binding.module, base_dir, workspace_root)
        if module_file is None:
            continue
        declaration = _index_file(module_file).get(binding.source_name)
        if declaration is not None and declaration.kind in (SymbolKind.STRUCT, SymbolKind.TYPE_ALIAS):
            known_types.add(binding.name)

    for line_number, line in enumerate(source.splitlines()):
        for match in re.finditer(r'\b(struct|type)\s+([A-Z][A-Za-z0-9_]*)', line):
            raw_tokens.append((line_number, match.start(1), len(match.group(1)), "keyword", []))
            token_type = "class" if match.group(1) == "struct" else "type"
            raw_tokens.append((line_number, match.start(2), len(match.group(2)), token_type, ["declaration"]))
        for match in re.finditer(r'\b(?:export\s+)?(?:(declare)\s+)?(let|const|static)\s+([a-z_][A-Za-z0-9_]*|\$[A-Za-z0-9_]+)', line):
            if match.group(1):
                raw_tokens.append((line_number, match.start(1), len(match.group(1)), "keyword", []))
            raw_tokens.append((line_number, match.start(2), len(match.group(2)), "keyword", []))
            suffix = line[match.end(3):]
            token_type = "function" if re.match(r'\s*(?:<[^>]+>\s*)?=\s*\(', suffix) or match.group(1) else "parameter"
            modifiers = ["declaration"]
            if match.group(2) == "const":
                modifiers.append("readonly")
            raw_tokens.append((line_number, match.start(3), len(match.group(3)), token_type, modifiers))
        for match in CALL_RE.finditer(line):
            modifiers = ["async"] if match.group(1) in suspend_names else []
            raw_tokens.append((line_number, match.start(1), len(match.group(1)), "function", modifiers))
            args_text, args_start = _call_args_on_line(line, match.end() - 1)
            if args_text is not None:
                for arg_match in re.finditer(r'\b([a-z_][A-Za-z0-9_]*|\$[A-Za-z0-9_]+)(?=\s*=)(?!\s*=>)', args_text):
                    raw_tokens.append((line_number, args_start + arg_match.start(1), len(arg_match.group(1)), "parameter", []))
        for match in re.finditer(r'\b([A-Z][A-Za-z0-9_]*)\b', line):
            name = match.group(1)
            if name in known_types or name in TYPE_COMPLETIONS:
                raw_tokens.append((line_number, match.start(1), len(name), "type", []))
    return _encode_semantic_tokens(raw_tokens)


def _encode_semantic_tokens(tokens: list[tuple[int, int, int, str, list[str]]]) -> list[int]:
    encoded: list[int] = []
    previous_line = 0
    previous_start = 0
    seen: set[tuple[int, int, int]] = set()
    for line, start, length, token_type, modifiers in sorted(tokens):
        key = (line, start, length)
        if key in seen or length <= 0:
            continue
        seen.add(key)
        delta_line = line - previous_line
        delta_start = start - previous_start if delta_line == 0 else start
        modifier_bits = 0
        for modifier in modifiers:
            modifier_index = SEMANTIC_TOKEN_MODIFIER_INDEX.get(modifier)
            if modifier_index is not None:
                modifier_bits |= 1 << modifier_index
        encoded.extend([delta_line, delta_start, length, SEMANTIC_TOKEN_TYPE_INDEX[token_type], modifier_bits])
        previous_line = line
        previous_start = start
    return encoded


def _call_args_on_line(line: str, open_paren: int) -> tuple[str | None, int]:
    depth = 0
    in_string = False
    escape = False
    for index in range(open_paren, len(line)):
        ch = line[index]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return line[open_paren + 1:index], open_paren + 1
    return None, open_paren + 1


def _declaration_kind_from_line(line: str, fallback: SymbolKind, name_end: int) -> SymbolKind:
    """根据声明右侧形态区分函数、变量、常量和 static。"""
    if fallback != SymbolKind.VARIABLE:
        return fallback
    prefix = line[:name_end]
    suffix = line[name_end:]
    if re.match(r"\s*(?:<[^>]+>\s*)?=\s*\(", suffix):
        return SymbolKind.FUNCTION
    if re.search(r"\bconst\b", prefix):
        return SymbolKind.CONSTANT
    if re.search(r"\bstatic\b", prefix):
        return SymbolKind.STATIC
    return SymbolKind.VARIABLE


def _parse_syntax_errors(source: str) -> list[SyntaxDiagnostic]:
    collector = _SyntaxErrorCollector()
    lexer = EzLangLexer(InputStream(source))
    lexer.removeErrorListeners()
    lexer.addErrorListener(collector)
    stream = CommonTokenStream(lexer)
    parser = EzLangParser(stream)
    parser.removeErrorListeners()
    parser.addErrorListener(collector)
    parser.compilationUnit()
    return collector.errors


def _syntax_diagnostic(error: SyntaxDiagnostic, source: str) -> dict[str, Any]:
    line = max(error.line - 1, 0)
    column = max(error.column, 0)
    token_length = len(error.token_text) if error.token_text and error.token_text != "<EOF>" else 1
    return {
        "range": {"start": {"line": line, "character": column}, "end": {"line": line, "character": column + token_length}},
        "severity": DIAGNOSTIC_ERROR,
        "source": "ezlang",
        "message": error.message,
    }


def _line_diagnostic(message: str, source: str, severity: int) -> dict[str, Any]:
    line_match = re.search(r"行\s+(\d+)", message)
    line = max(int(line_match.group(1)) - 1, 0) if line_match else 0
    line_text = source.splitlines()[line] if line < len(source.splitlines()) else ""
    end = max(len(line_text), 1)
    return {
        "range": {"start": {"line": line, "character": 0}, "end": {"line": line, "character": end}},
        "severity": severity,
        "source": "ezlang",
        "message": message,
    }


def _symbol_completion(symbol: Symbol) -> dict[str, Any]:
    kind = COMPLETION_KIND_VARIABLE
    if symbol.kind == SymbolKind.FUNCTION:
        kind = COMPLETION_KIND_FUNCTION
    elif symbol.kind == SymbolKind.STRUCT:
        kind = COMPLETION_KIND_STRUCT
    elif symbol.kind == SymbolKind.TYPE_ALIAS:
        kind = COMPLETION_KIND_TYPE
    detail = str(symbol.type) if symbol.type is not None else symbol.kind.name.lower()
    return {"label": symbol.name, "kind": kind, "detail": detail}


def _declaration_completion(declaration: Declaration) -> dict[str, Any]:
    kind = COMPLETION_KIND_VARIABLE
    if declaration.kind == SymbolKind.FUNCTION:
        kind = COMPLETION_KIND_FUNCTION
    elif declaration.kind == SymbolKind.STRUCT:
        kind = COMPLETION_KIND_STRUCT
    elif declaration.kind == SymbolKind.TYPE_ALIAS:
        kind = COMPLETION_KIND_TYPE
    return {"label": declaration.name, "kind": kind, "detail": declaration.kind.name.lower()}


def _symbol_markdown(symbol: Symbol) -> str:
    detail = str(symbol.type) if symbol.type is not None else symbol.kind.name.lower()
    return f"```ez\n{symbol.name}: {detail}\n```\n\n{symbol.kind.name.lower()}"


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        label = item.get("label")
        if label in seen:
            continue
        seen.add(label)
        result.append(item)
    return result


def _declaration_symbol(declaration: Declaration, uri: str) -> dict[str, Any]:
    location = declaration.location(uri)
    return {
        "name": declaration.name,
        "kind": _symbol_kind(declaration.kind),
        "location": location,
        "containerName": "",
    }


def _symbol_kind(kind: SymbolKind) -> int:
    if kind == SymbolKind.FUNCTION:
        return SYMBOL_KIND_FUNCTION
    if kind == SymbolKind.STRUCT:
        return SYMBOL_KIND_STRUCT
    if kind == SymbolKind.TYPE_ALIAS:
        return SYMBOL_KIND_TYPE
    if kind == SymbolKind.CONSTANT:
        return SYMBOL_KIND_CONSTANT
    return SYMBOL_KIND_VARIABLE


def _import_bindings(source: str) -> list[ImportBinding]:
    bindings: list[ImportBinding] = []
    for match in IMPORT_RE.finditer(source):
        module = match.group(1)
        specs = match.group(2)
        line = source[:match.start(2)].count("\n")
        line_start = source.rfind("\n", 0, match.start(2)) + 1
        for spec_match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*|\$[A-Za-z0-9_]+)(?:\s+as\s+([A-Za-z_][A-Za-z0-9_]*|\$[A-Za-z0-9_]+))?", specs):
            source_name = spec_match.group(1)
            imported = spec_match.group(2) or source_name
            absolute = match.start(2) + spec_match.start(2 if spec_match.group(2) else 1)
            bindings.append(ImportBinding(imported, source_name, module, line, absolute - line_start))
    return bindings


def _index_file(path: Path) -> dict[str, Declaration]:
    try:
        return index_document(path.read_text(encoding="utf-8"), _uri_from_path(path))
    except OSError:
        return {}


def _resolve_module_path(module: str, base_dir: Path, workspace_root: Path) -> Path | None:
    candidates: list[Path] = []
    module_path = Path(module)
    if module.startswith("std/"):
        candidates.append(ROOT / "packages" / (module + ".ez"))
        candidates.append(workspace_root / "packages" / (module + ".ez"))
    elif module_path.is_absolute():
        candidates.append(module_path)
        candidates.append(module_path.with_suffix(".ez"))
    else:
        candidates.append(base_dir / module)
        candidates.append(base_dir / (module + ".ez"))
        candidates.append(base_dir / module / "index.ez")
        candidates.append(workspace_root / module)
        candidates.append(workspace_root / (module + ".ez"))
        candidates.append(workspace_root / module / "index.ez")
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def _full_document_range(source: str) -> dict[str, Any]:
    lines = source.splitlines()
    if not lines:
        return {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}}
    return {
        "start": {"line": 0, "character": 0},
        "end": {"line": len(lines) - 1, "character": len(lines[-1])},
    }


def _line_prefix(source: str, line: int, character: int) -> str:
    lines = source.splitlines()
    if line < 0 or line >= len(lines):
        return ""
    return lines[line][:character]


def _word_at(source: str, line: int, character: int) -> str:
    lines = source.splitlines()
    if line < 0 or line >= len(lines):
        return ""
    current = lines[line]
    character = min(max(character, 0), len(current))
    left = character
    while left > 0 and re.match(r"[A-Za-z0-9_$]", current[left - 1]):
        left -= 1
    right = character
    while right < len(current) and re.match(r"[A-Za-z0-9_$]", current[right]):
        right += 1
    return current[left:right]


def _path_from_uri(uri: str) -> Path | None:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    path = unquote(parsed.path)
    if os.name == "nt" and path.startswith("/") and re.match(r"/[A-Za-z]:", path):
        path = path[1:]
    return Path(path)


def _uri_from_path(path: Path) -> str:
    return path.resolve().as_uri()


def main() -> int:
    return EzLanguageServer().serve()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
