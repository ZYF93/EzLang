"""
TDD tests for EzLang Functions (Named Args, Default Args, Explicit Returns).
"""

import pytest
from ezlang.compiler import EzLangCompiler
from ezlang.lexer import EzLangLexerWrapper
from ezlang.parser import EzLangParserWrapper
from ezlang.semantic_analyzer import SemanticAnalyzer


def analyze(source: str):
    lexer = EzLangLexerWrapper(source)
    parser = EzLangParserWrapper(lexer.tokens)
    analyzer = SemanticAnalyzer(parser.get_ast())
    analyzer.analyze()
    return analyzer


def test_ir_function_definition():
    """验证表达式体函数定义仍然可用"""
    compiler = EzLangCompiler()
    source = "const add = (a: I32, b: I32) => a + b;"
    ir_code = compiler.compile(source)

    assert 'define i32 @"add"(i32 %"a", i32 %"b")' in ir_code
    assert 'add i32 %"a", %"b"' in ir_code


def test_ir_named_argument_call_reorders_arguments():
    """验证命名参数调用会按形参顺序重排"""
    compiler = EzLangCompiler()
    source = "const add = (a: I32, b: I32) => { return a + b; }; let res = add(b = 2, a = 10);"
    ir_code = compiler.compile(source)

    assert 'call i32 @"add"(i32 10, i32 2)' in ir_code


def test_ir_default_argument_is_filled_when_omitted():
    """验证省略参数时会使用默认值"""
    compiler = EzLangCompiler()
    source = "const add = (a: I32, b: I32 = 1) => { return a + b; }; let res = add(a = 10);"
    ir_code = compiler.compile(source)

    assert 'call i32 @"add"(i32 10, i32 1)' in ir_code


def test_ir_explicit_return_statement():
    """验证函数体必须通过 return 显式返回"""
    compiler = EzLangCompiler()
    source = "const get_val = () => { let x = 42; return x; };"
    ir_code = compiler.compile(source)

    assert 'define i32 @"get_val"()' in ir_code
    assert 'ret i32' in ir_code


def test_ir_recursion_fibonacci():
    """验证递归调用（斐波那契示例）"""
    compiler = EzLangCompiler()
    source = """
    const fib = (n: I32) => {
        return (n <= 1) ? n : fib(n = n - 1) + fib(n = n - 2);
    };
    """
    ir_code = compiler.compile(source)

    assert ir_code.count('call i32 @"fib"') >= 2
    assert 'ret i32' in ir_code


def test_semantic_missing_required_function_argument():
    """验证缺失必填参数时报错"""
    source = "const add = (a: I32, b: I32 = 1) => a + b; let res = add(b = 2);"

    with pytest.raises(Exception, match="Missing required argument 'a' for function 'add'"):
        analyze(source)


def test_semantic_positional_argument_is_forbidden():
    """验证函数调用禁止位置参数"""
    source = "const add = (a: I32, b: I32) => a + b; let res = add(1, 2);"

    with pytest.raises(Exception, match="Positional arguments are not allowed for function 'add'"):
        analyze(source)


def test_semantic_implicit_block_return_is_forbidden():
    """验证块函数体不再支持最后一个表达式隐式返回"""
    source = "const get_val = () => { let x = 42; x; };"

    with pytest.raises(Exception, match="Function 'get_val' must use an explicit return statement"):
        analyze(source)
