"""
TDD tests for EzLang Functions (Definitions, Calls, Parameters, Returns).
"""

import pytest
from ezlang.compiler import EzLangCompiler

def test_ir_function_definition():
    """验证基础函数定义生成 define 指令"""
    compiler = EzLangCompiler()
    source = "const add = (a: I32, b: I32) => a + b;"
    ir_code = compiler.compile(source)
    
    # 验证是否生成了带参数的函数定义
    assert 'define i32 @"add"(i32 %"a", i32 %"b")' in ir_code
    assert 'add i32 %"a", %"b"' in ir_code

def test_ir_function_call():
    """验证函数调用生成 call 指令"""
    compiler = EzLangCompiler()
    source = "const add = (a: I32) => a + 1; let res = add(10);"
    ir_code = compiler.compile(source)
    
    assert 'call i32 @"add"(i32 10)' in ir_code

def test_ir_expression_return():
    """验证函数体最后一个表达式作为返回值"""
    compiler = EzLangCompiler()
    source = "const get_val = () => { let x = 42; x; };"
    ir_code = compiler.compile(source)
    
    # 验证返回值是否正确 (目前实现中，局部变量会被折叠为常量值)
    assert 'ret i32 42' in ir_code

def test_ir_recursion_fibonacci():
    """验证递归调用（斐波那契示例）"""
    compiler = EzLangCompiler()
    source = """
    const fib = (n: I32) => {
        (n <= 1) ? n : fib(n - 1) + fib(n - 2)
    };
    """
    ir_code = compiler.compile(source)
    
    assert 'call i32 @"fib"' in ir_code
    assert 'ret i32' in ir_code
