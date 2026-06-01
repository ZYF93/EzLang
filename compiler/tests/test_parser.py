"""EzLang 解析器测试 - 验证所有示例文件和语法特性"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from antlr4 import InputStream, CommonTokenStream
from antlr4.error.ErrorListener import ErrorListener
from parser.EzLangLexer import EzLangLexer
from parser.EzLangParser import EzLangParser


class ErrorCollector(ErrorListener):
    """收集语法错误的监听器"""

    def __init__(self):
        self.errors = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append(f'行 {line}:{column} - {msg}')

    def reportAmbiguity(self, recognizer, dfa, startIndex, stopIndex, exact, ambigAlts, configs):
        pass

    def reportAttemptingFullContext(self, recognizer, dfa, startIndex, stopIndex, conflictingAlts, configs):
        pass

    def reportContextSensitivity(self, recognizer, dfa, startIndex, stopIndex, prediction, configs):
        pass


def parse_source(source: str):
    """解析 EzLang 源码字符串"""
    errors = ErrorCollector()
    lexer = EzLangLexer(InputStream(source))
    token_stream = CommonTokenStream(lexer)
    parser = EzLangParser(token_stream)
    parser.removeErrorListeners()
    parser.addErrorListener(errors)
    tree = parser.compilationUnit()
    return tree, errors.errors


def parse_file(filepath: str):
    """解析 .ez 文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return parse_source(f.read())


def all_example_files():
    """获取所有示例文件路径"""
    examples_dir = Path(__file__).parent.parent.parent / 'examples'
    return sorted(examples_dir.glob('*.ez'))


class TestParser:

    def test_empty_source(self):
        """测试空源码"""
        tree, errors = parse_source('')
        assert len(errors) == 0, f'解析错误: {errors}'
        assert tree is not None

    def test_hello(self):
        """测试 hello.ez"""
        tree, errors = parse_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'hello.ez'))
        assert len(errors) == 0, f'解析错误: {errors}'

    def test_basics(self):
        """测试 basics.ez - 基础语法"""
        tree, errors = parse_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'basics.ez'))
        assert len(errors) == 0, f'解析错误: {errors}'

    def test_types(self):
        """测试 types.ez - 类型系统"""
        tree, errors = parse_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'types.ez'))
        assert len(errors) == 0, f'解析错误: {errors}'

    def test_structs(self):
        """测试 structs.ez - 结构体"""
        tree, errors = parse_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'structs.ez'))
        assert len(errors) == 0, f'解析错误: {errors}'

    def test_functions(self):
        """测试 functions.ez - 函数与表达式"""
        tree, errors = parse_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'functions.ez'))
        assert len(errors) == 0, f'解析错误: {errors}'

    def test_control(self):
        """测试 control.ez - 流程控制"""
        tree, errors = parse_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'control.ez'))
        assert len(errors) == 0, f'解析错误: {errors}'

    def test_operators(self):
        """测试 operators.ez - 运算符"""
        tree, errors = parse_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'operators.ez'))
        assert len(errors) == 0, f'解析错误: {errors}'

    def test_simd(self):
        """测试 simd.ez - SIMD 向量"""
        tree, errors = parse_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'simd.ez'))
        assert len(errors) == 0, f'解析错误: {errors}'

    def test_vars(self):
        """测试 vars.ez - 变量声明"""
        tree, errors = parse_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'vars.ez'))
        assert len(errors) == 0, f'解析错误: {errors}'

    def test_arena(self):
        """测试 arena.ez - 内存模型"""
        tree, errors = parse_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'arena.ez'))
        assert len(errors) == 0, f'解析错误: {errors}'

    def test_flow(self):
        """测试 flow.ez - Flow 并发语义"""
        tree, errors = parse_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'flow.ez'))
        assert len(errors) == 0, f'解析错误: {errors}'

    def test_modules(self):
        """测试 modules.ez - 模块系统"""
        tree, errors = parse_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'modules.ez'))
        assert len(errors) == 0, f'解析错误: {errors}'

    def test_markup_literal(self):
        """测试 XML 风格标记语法"""
        tree, errors = parse_source('''
        let ui = <text color="blue">
            "Welcome"
            <div id=1 />
            {1 + 2}
        </text>;
        ''')
        assert len(errors) == 0, f'解析错误: {errors}'

    def test_decorator_variable_decl(self):
        """测试变量声明装饰器语法"""
        tree, errors = parse_source('''
        const log = (this: Meta<I32>): Void => { return; };
        @log let watched = 1;
        ''')
        assert len(errors) == 0, f'解析错误: {errors}'

    def test_all_examples(self):
        """测试所有示例文件可解析"""
        for ez_file in all_example_files():
            tree, errors = parse_file(str(ez_file))
            assert len(errors) == 0, f'{ez_file.name}: {errors}'
