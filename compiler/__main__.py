"""
EzLang 编译器 CLI 入口。
支持 parse / compile / check 子命令。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from antlr4 import CommonTokenStream, FileStream, InputStream

from compiler.errors import ErrorCollector, Severity
from compiler.context import CompileContext, TargetConfig

# ANTLR4 generated imports
from compiler.generated.EzLangLexer import EzLangLexer
from compiler.generated.EzLangParser import EzLangParser
from compiler.visitor import ASTBuilder


class EzLangErrorListener:
    """ANTLR4 错误监听器，将语法错误转发到 ErrorCollector。"""

    def __init__(self, collector: ErrorCollector):
        self.collector = collector

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.collector.error(
            message=f"语法错误: {msg}",
            line=line,
            column=column,
        )

    def reportAmbiguity(self, *args):
        pass

    def reportAttemptingFullContext(self, *args):
        pass

    def reportContextSensitivity(self, *args):
        pass


def parse_file(filepath: str, collector: ErrorCollector):
    """
    解析 .ez 源文件，返回 ANTLR4 parse tree。
    """
    input_stream = FileStream(filepath, encoding="utf-8")

    lexer = EzLangLexer(input_stream)
    lexer.removeErrorListeners()
    lexer.addErrorListener(EzLangErrorListener(collector))

    token_stream = CommonTokenStream(lexer)

    parser = EzLangParser(token_stream)
    parser.removeErrorListeners()
    parser.addErrorListener(EzLangErrorListener(collector))

    tree = parser.program()
    return tree


def build_ast(filepath: str, collector: ErrorCollector):
    """
    解析源文件并构建 AST。
    """
    tree = parse_file(filepath, collector)
    if collector.has_errors:
        return None

    builder = ASTBuilder(file=filepath)
    ast = builder.visit(tree)
    return ast


def cmd_parse(args):
    """parse 子命令：解析文件并打印语法树。"""
    filepath = args.file
    source = Path(filepath).read_text(encoding="utf-8")
    source_lines = source.splitlines()
    collector = ErrorCollector(source_lines=source_lines, file=filepath)

    tree = parse_file(filepath, collector)

    if collector.has_errors:
        collector.report()
        sys.exit(1)

    print(f"✅ 解析成功: {filepath}")
    print(tree.toStringTree(recog=None))


def cmd_ast(args):
    """ast 子命令：解析文件并打印 AST。"""
    filepath = args.file
    source = Path(filepath).read_text(encoding="utf-8")
    source_lines = source.splitlines()
    collector = ErrorCollector(source_lines=source_lines, file=filepath)

    ast = build_ast(filepath, collector)

    if collector.has_errors:
        collector.report()
        sys.exit(1)

    print(f"✅ AST 构建成功: {filepath}")
    _print_ast(ast, indent=0)


def cmd_compile(args):
    """compile 子命令：编译文件并输出 LLVM IR。"""
    filepath = args.file
    source = Path(filepath).read_text(encoding="utf-8")
    source_lines = source.splitlines()
    collector = ErrorCollector(source_lines=source_lines, file=filepath)

    ast = build_ast(filepath, collector)

    if collector.has_errors:
        collector.report()
        sys.exit(1)

    target = TargetConfig(
        arch=args.arch or "x86_64",
        os=args.os or "linux",
        output_dir=args.output or "./dist"
    )
    ctx = CompileContext(module_name=Path(filepath).stem, target=target)

    # TODO: 阶段二实现 codegen
    print(f"✅ 编译成功: {filepath}")
    print(ctx.dump_ir())


def cmd_check(args):
    """check 子命令：批量检查 examples/ 目录下所有 .ez 文件。"""
    examples_dir = Path(args.dir or "examples")
    if not examples_dir.exists():
        print(f"❌ 目录不存在: {examples_dir}")
        sys.exit(1)

    files = sorted(examples_dir.glob("*.ez"))
    if not files:
        print(f"⚠️ 没有找到 .ez 文件: {examples_dir}")
        return

    passed = 0
    failed = 0

    for f in files:
        source = f.read_text(encoding="utf-8")
        source_lines = source.splitlines()
        collector = ErrorCollector(source_lines=source_lines, file=str(f))

        tree = parse_file(str(f), collector)

        if collector.has_errors:
            print(f"  ❌ {f.name}")
            collector.report(use_color=True)
            failed += 1
        else:
            print(f"  ✅ {f.name}")
            passed += 1

    print(f"\n{'='*40}")
    print(f"总计: {passed + failed} 个文件, ✅ {passed} 通过, ❌ {failed} 失败")

    if failed > 0:
        sys.exit(1)


def _print_ast(node, indent=0):
    """递归打印 AST 节点（调试用途）。"""
    prefix = "  " * indent
    if node is None:
        print(f"{prefix}None")
        return

    class_name = type(node).__name__
    # 获取非默认的字段
    from dataclasses import fields
    field_strs = []
    for f in fields(node):
        if f.name == "span":
            continue
        val = getattr(node, f.name)
        if isinstance(val, list):
            if val:
                field_strs.append(f"{f.name}=[...]")
        elif isinstance(val, (str, int, float, bool)):
            field_strs.append(f"{f.name}={val!r}")

    attrs = ", ".join(field_strs)
    print(f"{prefix}{class_name}({attrs})")

    # 递归打印子节点
    from dataclasses import fields as df
    for f in df(node):
        if f.name == "span":
            continue
        val = getattr(node, f.name)
        if isinstance(val, list):
            for item in val:
                if hasattr(item, '__dataclass_fields__'):
                    _print_ast(item, indent + 1)
        elif hasattr(val, '__dataclass_fields__') and not isinstance(val, (str, int, float, bool)):
            _print_ast(val, indent + 1)


def main():
    parser = argparse.ArgumentParser(
        prog="ezlang",
        description="EzLang Compiler — 编译器命令行工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # parse
    p_parse = subparsers.add_parser("parse", help="解析 .ez 文件并打印语法树")
    p_parse.add_argument("file", help="源文件路径")

    # ast
    p_ast = subparsers.add_parser("ast", help="解析文件并打印 AST")
    p_ast.add_argument("file", help="源文件路径")

    # compile
    p_compile = subparsers.add_parser("compile", help="编译 .ez 文件为 LLVM IR")
    p_compile.add_argument("file", help="源文件路径")
    p_compile.add_argument("--arch", help="目标架构 (默认: x86_64)")
    p_compile.add_argument("--os", help="目标操作系统 (默认: linux)")
    p_compile.add_argument("--output", "-o", help="输出目录")

    # check
    p_check = subparsers.add_parser("check", help="批量检查 .ez 文件语法")
    p_check.add_argument("--dir", "-d", help="源文件目录 (默认: examples)")

    args = parser.parse_args()

    if args.command == "parse":
        cmd_parse(args)
    elif args.command == "ast":
        cmd_ast(args)
    elif args.command == "compile":
        cmd_compile(args)
    elif args.command == "check":
        cmd_check(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
